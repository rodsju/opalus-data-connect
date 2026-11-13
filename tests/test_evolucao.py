"""Evolução clínica: pendências por regra, campos do formulário, payload da IA e rotas -- sem Oracle."""

import datetime
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import ia  # noqa: E402
from src.consultas import evolucao  # noqa: E402
from src.reports import evolucao_campos, evolucao_ia  # noqa: E402

dt = datetime.datetime


def linha(**kw):
    base = {"id_admissao": 10, "id_paciente": 99, "paciente_codigo": "P99", "unidade": "U HSP", "tipo": 0,
            "operadora": "Op A", "entrada": dt(2026, 8, 1), "saida": None, "dias_no_periodo": 30, "evolucoes": 20,
            "evolucoes_medicas": 3, "ultima_medica": dt(2026, 9, 28), "intercorrencias": 0, "interc_sem_evolucao": 0,
            "prescricoes": 1, "presc_sem_evolucao": 0}
    return {**base, **kw}


def test_pendencias_por_regra():
    assert evolucao.pendencias(linha()) == []
    assert evolucao.pendencias(linha(evolucoes_medicas=0)) == ["Sem evolução médica no mês"]
    # Entrou no último dia: ainda não é pendência
    assert evolucao.pendencias(linha(evolucoes_medicas=0, dias_no_periodo=1)) == []
    assert evolucao.pendencias(linha(interc_sem_evolucao=2, presc_sem_evolucao=1)) == [
        "2 intercorrências sem evolução médica em 48 h", "1 prescrição médica sem evolução médica"]


def test_lista_filtros_resumo_e_link():
    linhas = evolucao.montar_linhas([linha(), linha(id_admissao=11, evolucoes_medicas=0),
                                     linha(id_admissao=12, interc_sem_evolucao=1)], "2026-09",
                                    {12: {"tendencia": "piorando", "conclusao": "Risco de internação: alto",
                                          "conclusao_chave": "alto"}})
    assert linhas[0]["situacao"] == "Em dia" and linhas[1]["situacao"] == "Com pendência"
    assert linhas[0]["detalhe"] == "/consultas/evolucao/10?mes=2026-09"
    assert linhas[2]["tendencia"] == "piorando" and linhas[0]["tendencia"] is None
    passa = lambda **f: [l["id_admissao"] for l in linhas if evolucao._passa(l, f)]  # noqa: E731
    assert passa(pendencia="com") == [11, 12] and passa(pendencia="sem") == [10]
    assert passa(pendencia="sem_medica") == [11] and passa(pendencia="intercorrencia") == [12]
    assert passa(tendencia="piorando") == [12] and passa(tendencia="nao_analisado") == [10, 11]
    assert passa(busca="11") == [11] and passa(busca="P99") == [10, 11, 12]
    kpis = {k["rotulo"]: k["valor"] for k in evolucao.resumo(linhas)}
    assert kpis["Com pendência"] == 2 and kpis["Piorando (IA)"] == 1 and kpis["Risco alto de internação (IA)"] == 1
    assert linhas[2]["conclusao"] == "Risco de internação: alto"


def test_nome_do_paciente_so_na_tela():
    cols = [c for c in evolucao.CONSULTA["colunas"] if c.get("formato") == "nome_paciente"]
    assert cols and all(c.get("so_tela") for c in cols)


ROTULOS = {
    "QUADROCLINICO": {"rotulo": "Quadro clínico", "dominio": None, "checkbox": None},
    "MED_SISTRESP_PAD_RESPIR": {"rotulo": "Tipo de Respiração", "checkbox": None,
                                "dominio": "value|0|.|10|Eupneico|20|Taquipneico"},
    "MED_SISTRESP_TQT": {"rotulo": "TQT:", "checkbox": 1, "dominio": "positional|0|não|1|sim"},
    "FEBRE": {"rotulo": "Febre", "checkbox": 1, "dominio": None},
    "DIAG_X": {"rotulo": "Diagnóstico X", "checkbox": None, "dominio": "positional|0|não|1|sim"},
    "INFECCAO": {"rotulo": "Infecção em tratamento?", "checkbox": None, "dominio": "value|-1|.|0|Não|1|Sim"},
    "PRES_SISTOLICA": {"rotulo": "PA sistólica", "checkbox": None, "dominio": None},
    "EVOL_REPONSAVEL": {"rotulo": "Responsável", "checkbox": None, "dominio": None},
}


def test_campos_do_formulario():
    assert evolucao_campos.dominio("value|0|.|10|Eupneico") == {"0": ".", "10": "Eupneico"}
    c = evolucao_campos.campos({"IDEVOLUTION": 1, "QUADROCLINICO": "<p>Estável&nbsp;</p>", "MED_SISTRESP_PAD_RESPIR": 20,
                                "MED_SISTRESP_TQT": 1, "FEBRE": 0, "PRES_SISTOLICA": 120.0,
                                "EVOL_REPONSAVEL": "Dra. Fulana", "SEM_ROTULO": "x", "DIAG_X": 0,
                                "INFECCAO": 0}, ROTULOS)
    assert c == {"Quadro clínico": "Estável", "Tipo de Respiração": "Taquipneico", "TQT": "sim", "PA sistólica": "120",
                 "Infecção em tratamento?": "Não"}


def test_so_o_que_mudou():
    evs = [{"formulario_chave": 238, "campos": {"a": "1", "b": "2"}},
           {"formulario_chave": 238, "campos": {"a": "1", "b": "2"}},
           {"formulario_chave": 155, "campos": {"x": "9"}},
           {"formulario_chave": 238, "campos": {"a": "3"}}]
    evolucao_campos.com_mudancas(evs)
    assert evs[0]["base"] and evs[0]["mudou"] == {"a": "1", "b": "2"}
    assert not evs[1]["base"] and evs[1]["mudou"] == {}
    assert evs[2]["base"]
    assert evs[3]["mudou"] == {"a": "3", "b": "(apagado)"}


def test_higieniza_nome_cpf_telefone():
    texto = "Maria da Silva refere dor. CPF 123.456.789-00, filha (11) 98765-4321. SILVA estável."
    limpo = evolucao_campos.higienizar(texto, "Maria da Silva")
    assert "Maria" not in limpo and "SILVA" not in limpo and "123.456" not in limpo and "98765" not in limpo
    assert "[PACIENTE] refere dor" in limpo


def contexto(n=3):
    evs = [{"id_evolucao": 100 + i, "data": dt(2026, 9, 1, 10) + datetime.timedelta(hours=6 * i), "especialidade": "Médico(A)", "medica": 1,
            "formulario": "HSP - Evolução Médica", "formulario_chave": 238,
            "campos": {"Quadro clínico": f"Maria refere dor {i}"}} for i in range(n)]
    evolucao_campos.com_mudancas(evs)
    return {"admissao": {"id_admissao": 10, "paciente_codigo": "P99", "id_paciente": 99, "tipo_nome": "Home care"},
            "mes": "2026-09", "dias_no_periodo": 30, "pendencias": [], "evolucoes": evs,
            "intercorrencias": [{"inicio": dt(2026, 9, 2), "classificacao": "c) Febre", "nivel": 13, "sem_evolucao": 1}],
            "prescricoes": []}


def test_payload_sem_nome_e_dentro_do_teto():
    dados = json.loads(evolucao_ia.montar_payload(contexto(), "Maria Souza"))
    assert "Maria" not in json.dumps(dados, ensure_ascii=False)
    assert dados["paciente"]["codigo"] == "P99" and dados["evolucoes"][0]["tipo"] == "completa"
    assert dados["intercorrencias"][0]["sem_evolucao_medica_48h"] is True
    # Estourando o teto: as antigas perdem os campos, as recentes ficam
    grande = contexto(40)
    for e in grande["evolucoes"]:
        e["mudou"] = {"Quadro clínico": "x" * 500}
    texto = evolucao_ia.montar_payload(grande, None, teto=8_000)
    dados = json.loads(texto)
    assert len(texto.encode()) <= 8_000 and len(dados["evolucoes"]) == 40
    assert dados["evolucoes"][0].get("omitida") and "campos" in dados["evolucoes"][-1]
    # Médica antiga resiste mais que não médica antiga
    for e in grande["evolucoes"][:20]:
        e["medica"] = 0
    dados = json.loads(evolucao_ia.montar_payload(grande, None, teto=16_000))
    nao_medicas = [e for e in dados["evolucoes"][:20] if "campos" in e]
    medicas = [e for e in dados["evolucoes"][20:-5] if "campos" in e]
    assert len(medicas) > len(nao_medicas)


def analise(id_evolucao):
    return evolucao_ia.AnaliseEvolucao(tendencia="piorando", confianca="media", resumo="r", pendencias=[],
                                       sinais=[evolucao_ia.SinalIA(tipo="piora", evidencia="e",
                                                                   id_evolucao=id_evolucao, data="01/09")])


def test_conferir_recusa_evolucao_inventada():
    dados = json.loads(evolucao_ia.montar_payload(contexto(), None))
    assert evolucao_ia.conferir(analise(101), dados).tendencia == "piorando"
    assert evolucao_ia.conferir(analise(0), dados)
    with pytest.raises(ia.GeracaoFalhou):
        evolucao_ia.conferir(analise(999), dados)


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app
    from src.reports import fonte

    def falsa(nome, params, limite=None):
        if nome == "evolucao_pacientes":
            return [linha(), linha(id_admissao=11, evolucoes_medicas=0)]
        if nome == "evolucao_admissao":
            return [linha()] if params.get("ID") == 10 else []
        if nome == "evolucao_lista":
            return [{"id_evolucao": 1, "data": dt(2026, 9, 3, 9), "especialidade": "Médico(A)", "medica": 1,
                     "assinada": 1, "id_template": 238, "formulario": "HSP - Evolução Médica",
                     "tabela": "TDWD_VISITAS_HSP"}]
        if nome == "evolucao_rotulos":
            return [{"tabela": "TDWD_VISITAS_HSP", "campo": k, **v} for k, v in ROTULOS.items()]
        return []

    monkeypatch.setattr(fonte, "rodar", falsa)
    monkeypatch.setattr(fonte, "formulario", lambda t, ids: [{"idevolution": 1, "quadroclinico": "Dispneico"}])
    monkeypatch.setattr(evolucao_ia, "ultima", lambda i, m: None)
    monkeypatch.setattr(evolucao_ia, "tendencias", lambda ids, m: {})
    return TestClient(app)


def test_rotas(cliente):
    html = {"accept": "text/html"}
    r = cliente.get("/consultas/evolucao?mes=2026-09", headers=html)
    assert r.status_code == 200 and "/consultas/evolucao/10?mes=2026-09" in r.text and "Com pendência" in r.text
    r = cliente.get("/consultas/evolucao/10?mes=2026-09", headers=html)
    assert r.status_code == 200 and "Dispneico" in r.text and "Quadro clínico" in r.text
    assert cliente.get("/consultas/evolucao/2?mes=2026-09", headers=html).status_code == 404
    csv = cliente.get("/consultas/evolucao?mes=2026-09&formato=csv").text
    assert "P99" in csv and "Nome" not in csv.splitlines()[0]


def test_pergunta_por_tipo_de_atendimento():
    for tipo, campo in ((1, "risco_internacao"), (0, "desfecho_provavel"), (3, "meta")):
        texto = evolucao_ia.instrucoes(tipo)
        assert f'"{campo}"' in texto and "{" in texto  # o formato JSON sai com chaves simples
        assert campo in evolucao_ia.MODELOS[tipo].model_fields
    assert evolucao_ia.foco(99) is evolucao_ia.FOCOS[1]
    assert evolucao_ia.conclusao({"desfecho_provavel": "home_care"}) == ("home_care", "Desfecho provável: vai para home care")
    assert evolucao_ia.conclusao({"tendencia": "estavel"}) == (None, None)  # análise antiga


def test_contexto_por_tipo():
    fim = dt(2026, 10, 1)
    hist = evolucao.historico([
        {"id_admissao": 1, "tipo": 1, "entrada": dt(2026, 6, 1), "saida": dt(2026, 8, 10), "desfecho": 1},
        {"id_admissao": 2, "tipo": 1, "entrada": dt(2026, 8, 20), "saida": None, "desfecho": 0},
        {"id_admissao": 3, "tipo": 0, "entrada": dt(2026, 1, 1), "saida": dt(2026, 2, 1), "desfecho": 23}])
    assert [h["desfecho_nome"] for h in hist] == ["internação hospitalar", "em atendimento", "outro (código 23)"]
    assert evolucao.por_tipo({"tipo": 1}, hist, [], fim) == {"internacoes_90d": 1}
    assert evolucao.por_tipo({"tipo": 0, "entrada": dt(2026, 9, 11)}, hist, [], fim) == {"dias_internado": 20}
    sessoes = [{"data": dt(2026, 9, 2), "cancelada": 0, "compareceu": 0, "com_evolucao": 0},
               {"data": dt(2026, 9, 3), "cancelada": 0, "compareceu": 1, "com_evolucao": 1},
               {"data": dt(2026, 9, 4), "cancelada": 0, "compareceu": 1, "com_evolucao": 0},
               {"data": dt(2026, 9, 5), "cancelada": 1, "compareceu": 0, "com_evolucao": 0}]
    assert evolucao.resumo_sessoes(sessoes, agora=fim) == {"agendadas": 3, "compareceu": 2, "faltas": 1,
                                                         "canceladas": 1, "realizadas_sem_evolucao": 1}


# --------------------------------------------------------------------------
# Jev (Decisions API do OpenRouter)
# --------------------------------------------------------------------------


def test_perguntas_do_jev_por_tipo():
    hc, ht = evolucao_ia.perguntas(1), evolucao_ia.perguntas(0)
    assert hc["risco_internacao"]["type"] == "score" and len(hc["risco_internacao"]["criteria"]) == 3
    assert ht["desfecho_provavel"]["type"] == "choice" and "home_care" in ht["desfecho_provavel"]["criteria"]
    assert set(hc) == {"risco_internacao", "tendencia", "alerta"} and hc["alerta"]["type"] == "noul"


def test_resposta_do_jev_vira_o_resultado_gravado():
    tend = {"type": "choice", "choice": "piorando", "confidence": 0.7,
            "probabilities": {"piorando": 0.8, "estavel": 0.2}}
    hc = evolucao_ia.resultado_jev({
        "risco_internacao": {"type": "score", "score": 1.9, "confidence": 0.9,
                             "probabilities": {"0": 0.05, "1": 0.15, "2": 0.8}},
        "tendencia": tend, "alerta": {"type": "noul", "noul": 0.7}}, 1)
    assert hc["risco_internacao"] == "alto" and hc["tendencia"] == "piorando" and hc["confianca"] == "media"
    assert hc["motor"] == "jev" and hc["probabilidades"]["risco_internacao"]["alto"] == 0.8
    assert hc["resumo"] == "Risco de internação: alto (80%) · tendência piorando (80%) · sinal de alerta (70%)"
    assert [s_["tipo"] for s_ in hc["sinais"]] == ["alerta"] and hc["pendencias"] == []
    assert evolucao_ia.conclusao(hc) == ("alto", "Risco de internação: alto")
    ht = evolucao_ia.resultado_jev({
        "desfecho_provavel": {"type": "choice", "choice": "home_care", "confidence": 0.95,
                              "probabilities": {"home_care": 0.9, "alta_casa": 0.1}},
        "tendencia": {**tend, "confidence": 0.9}, "alerta": {"type": "noul", "noul": 0.1}}, 0)
    assert ht["desfecho_provavel"] == "home_care" and ht["confianca"] == "alta" and ht["sinais"] == []


def test_motor_entra_no_hash_e_jev_usa_decidir(monkeypatch):
    from src import provedores

    gravados = []

    class Con:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            gravados.append(params)

    jev = provedores.Provedor(slug="jev", nome="Jev", tipo="decisions", modelo="typesafe/jev-1.13", chave="k",
                              capacidade="decisao")
    monkeypatch.setattr(evolucao_ia.banco, "garantir_schema", lambda: None)
    monkeypatch.setattr(evolucao_ia.banco, "conexao", lambda: Con())
    monkeypatch.setattr(evolucao_ia, "ultima", lambda i, m: {"payload_hash": "outro"})
    monkeypatch.setattr(evolucao_ia, "escolher_motor", lambda par: jev)
    pedidos = []

    def decidir(prov, estado, perguntas):
        pedidos.append((estado, perguntas))
        return ({"risco_internacao": {"type": "score", "probabilities": {"0": 1, "1": 0, "2": 0}, "confidence": 1},
                 "tendencia": {"type": "choice", "choice": "estavel", "confidence": 1, "probabilities": {}},
                 "alerta": {"type": "noul", "noul": 0}}, {"input_tokens": 100, "output_tokens": 10})

    monkeypatch.setattr(evolucao_ia.ia, "decidir", decidir)
    ctx = contexto()
    ctx["admissao"]["tipo"] = 1
    evolucao_ia.analisar(ctx, "Maria Souza", par="jev::typesafe/jev-1.13")
    estado, _ = pedidos[0]
    assert "Maria" not in json.dumps(estado, ensure_ascii=False) and estado["paciente"]["codigo"] == "P99"
    resultado = json.loads(gravados[0][6])
    assert resultado["risco_internacao"] == "baixo" and resultado["motor"] == "jev"
    payload = evolucao_ia.montar_payload(ctx, "Maria Souza", teto=evolucao_ia.TETO_JEV)
    import hashlib
    assert gravados[0][5] == hashlib.sha256((jev.valor + payload).encode()).hexdigest()
    assert gravados[0][5] != hashlib.sha256(payload.encode()).hexdigest()


def test_provedor_de_decisao_so_com_tipo_decisions():
    from src import provedores

    provedores.validar("Jev", "decisions", ["typesafe/jev-1.13"], "decisao", "k", criando=True)
    for tipo, capacidade in (("openai", "decisao"), ("decisions", "llm")):
        with pytest.raises(provedores.ConfiguracaoInvalida):
            provedores.validar("Jev", tipo, ["m"], capacidade, "k", criando=True)


def test_decidir_repete_o_transitorio(monkeypatch):
    from src import provedores

    prov = provedores.Provedor(slug="jev", nome="Jev", tipo="decisions", modelo="m", chave="k", capacidade="decisao")
    respostas = [ia.GeracaoFalhou("Limite de requisições atingido, tente de novo"),
                 {"answers": {"a": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 5}}]

    def post(_prov, corpo):
        r = respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(ia, "_post_decisao", post)
    monkeypatch.setattr(ia.time, "sleep", lambda s: None)
    assert ia.decidir(prov, {"x": 1}, {"a": {}}) == ({"a": {"type": "noul", "noul": 0.9}}, {"input_tokens": 5})
    monkeypatch.setattr(ia, "_post_decisao", lambda p, c: (_ for _ in ()).throw(ia.GeracaoFalhou("A chave de 'jev' foi recusada")))
    with pytest.raises(ia.GeracaoFalhou):
        ia.decidir(prov, {"x": 1}, {"a": {}})
    monkeypatch.setattr(ia, "_post_decisao", lambda p, c: {"answers": {}})
    with pytest.raises(ia.GeracaoFalhou, match="todas as perguntas"):
        ia.decidir(prov, {"x": 1}, {"a": {}})
