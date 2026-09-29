"""Orçamentos detalhados: regras de risco, orçado × faturado, IA conferida e rotas -- sem Oracle."""

import datetime
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import ia  # noqa: E402
from src.consultas import orcamentos as orcamentos_detalhe  # noqa: E402
from src.reports import orcamento_ia, orcamento_risco  # noqa: E402

d = datetime.date


def orc(**kw):
    base = {"id_orcamento": 1, "id_admissao": 10, "id_paciente": 99, "unidade": "U HSP", "operadora": "Op A",
            "particular": 0, "inicio": d(2026, 5, 1), "fim": d(2026, 5, 31), "situacao": "Autorizado (operadora)",
            "senha": "123", "validade_senha": d(2026, 12, 31), "itens": 3, "orcado": 100, "faturado": 100,
            "contas": 1, "contas_abertas": 1}
    return {**base, **kw}


def item(recurso_id, qtd, preco, coberta=0, **kw):
    return {"recurso_id": recurso_id, "recurso": f"R{recurso_id}", "categoria": "Medicamentos", "qtd": qtd,
            "qtd_coberta": coberta, "preco": preco, "bruto": preco * qtd, "pacote": preco * coberta,
            "cobrado": preco * (qtd - coberta), **kw}


def test_regras_da_lista():
    hoje = d(2026, 9, 1)
    assert orcamento_risco.avaliar(orc(), hoje=hoje) == []
    regras = {r["regra"]: r["severidade"] for r in orcamento_risco.avaliar(
        orc(senha="", validade_senha=d(2026, 5, 20), faturado=150),
        taxas_operadora={"Op A": {"taxa": 7.0, "motivo": "1705"}}, pacientes_glosados={99}, hoje=hoje)}
    assert regras == {"sem_senha": "alta", "senha_vence_antes": "alta", "faturado_acima": "media",
                      "operadora_glosa": "alta", "paciente_glosado": "media"}
    assert orcamento_risco.nivel([{"severidade": "media"}, {"severidade": "alta"}]) == "alta"
    assert orcamento_risco.nivel([]) is None


def test_senha_vencida_so_com_conta_aberta():
    hoje = d(2026, 9, 1)
    vencida = orc(validade_senha=d(2026, 8, 1), fim=d(2026, 7, 31))
    assert [r["regra"] for r in orcamento_risco.avaliar(vencida, hoje=hoje)] == ["senha_vencida"]
    assert orcamento_risco.avaliar({**vencida, "contas_abertas": 0}, hoje=hoje) == []


def test_comparar_itens_classifica_os_desvios():
    orcados = [item(1, 10, 5), item(2, 10, 5), item(3, 10, 5), item(4, 10, 5), item(5, 4, 10, coberta=4)]
    faturados = [item(1, 10, 5), item(2, 12, 5), item(3, 10, 6), item(6, 1, 50, glosa_iw=5)]
    tipos = {c["recurso_id"]: c["tipo"] for c in orcamento_risco.comparar_itens(orcados, faturados)}
    assert tipos == {1: "igual", 2: "qtd acima", 3: "preço diferente", 4: "orçado não faturado",
                     5: "igual", 6: "faturado sem orçar"}
    primeiro = orcamento_risco.comparar_itens(orcados, faturados)[0]
    assert primeiro["tipo"] == "faturado sem orçar" and primeiro["dif_valor"] == 50
    riscos = {r["regra"] for r in orcamento_risco.avaliar_itens(orcamento_risco.comparar_itens(orcados, faturados))}
    assert riscos == {"faturado sem orçar", "qtd acima", "preço diferente"}


def test_lista_filtra_por_foco_e_mostra_so_codigo():
    orcamentos = [orc(id_orcamento=1), orc(id_orcamento=2, contas_abertas=0, id_admissao=20),
                  orc(id_orcamento=3, situacao="Cancelado", contas=0, contas_abertas=0)]
    glosas = [{"id_admissao": 20, "competencia": d(2026, 5, 1), "glosa": 30, "motivo": "1705", "linhas": 1}]
    por_foco = {f: [l["id_orcamento"] for l in orcamentos_detalhe.montar_lista(
        orcamentos, glosas, {}, set(), set(), f, hoje=d(2026, 9, 1))["linhas"]]
        for f in orcamentos_detalhe.FOCOS}
    assert por_foco["prevenir"] == [1]
    assert por_foco["faturados"] == [2]
    assert por_foco["com_glosa"] == [2]
    assert sorted(por_foco["todos"]) == [1, 2, 3]
    linha = orcamentos_detalhe.montar_lista(orcamentos, glosas, {}, set(), set(), "todos")["linhas"][0]
    assert linha["paciente_codigo"] == "P99"


def contexto():
    comparacao = orcamento_risco.comparar_itens([item(1, 10, 5)], [item(1, 12, 5), item(2, 1, 40)])
    return {"orcamento": orc(), "paciente_codigo": "P99", "comparacao": comparacao,
            "riscos": orcamento_risco.avaliar_itens(comparacao),
            "historico_operadora": [{"motivo": "1705", "descricao": "VALOR APRESENTADO A MAIOR", "linhas": 3,
                                     "glosa": 90, "recuperado": 10, "perda": 20}],
            "glosas": []}


def test_payload_sem_nome_de_paciente():
    ctx = contexto()
    ctx["orcamento"]["nome_paciente"] = "FULANA DE TAL"   # mesmo que venha no dicionário, não sai
    payload = orcamento_ia.montar_payload(ctx, [{"codigo": "1705", "descricao": "X"}])
    assert "FULANA" not in payload and '"paciente_codigo": "P99"' in payload
    dados = json.loads(payload)
    assert {i["recurso"] for i in dados["itens"]} == {"R1", "R2"}


def analise(item_, motivo):
    return orcamento_ia.AnaliseOrcamento(resumo="r", riscos=[orcamento_ia.RiscoIA(
        tema="quantidade", item=item_, motivo_tiss=motivo, evidencia="e", recomendacao="c", severidade="alta")])


def test_conferir_recusa_item_ou_codigo_inventado():
    dados = json.loads(orcamento_ia.montar_payload(contexto(), []))
    assert orcamento_ia.conferir(analise("r1", "1705"), dados, {"1705"}).riscos[0].item == "r1"
    assert orcamento_ia.conferir(analise("", ""), dados, {"1705"})
    with pytest.raises(ia.GeracaoFalhou):
        orcamento_ia.conferir(analise("Item que não existe", ""), dados, {"1705"})
    with pytest.raises(ia.GeracaoFalhou):
        orcamento_ia.conferir(analise("R1", "9999"), dados, {"1705"})


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from src.main import app
    from src.reports import fonte

    def falsa(nome, params, limite=None):
        if nome == "orcamentos_lista":
            return [orc()]
        if nome == "orcamento_cabecalho":
            return [orc()] if params.get("ID") == 1 else []
        if nome == "orcamento_itens":
            return [item(1, 10, 5)]
        if nome == "orcamento_faturado_itens":
            return [item(1, 12, 5, glosa_iw=0)]
        return []

    monkeypatch.setattr(fonte, "rodar", falsa)
    monkeypatch.setattr(orcamentos_detalhe, "taxas_operadora", lambda: {})
    monkeypatch.setattr(orcamento_ia, "ultima", lambda i: None)
    return TestClient(app)


def test_rotas(cliente):
    html = {"accept": "text/html"}
    r = cliente.get("/consultas/orcamentos?mes=2026-05&foco=todos", headers=html)
    assert r.status_code == 200 and "/consultas/orcamentos/1" in r.text and "P99" in r.text
    r = cliente.get("/consultas/orcamentos/1", headers=html)
    assert r.status_code == 200 and "qtd acima" in r.text
    assert cliente.get("/consultas/orcamentos/2", headers=html).status_code == 404


def test_conta_paciente_um_orcamento_por_linha_e_glosa_uma_vez():
    from src.consultas import conta_paciente

    base = {"id_conta": 86751, "competencia": None, "pre_auditoria": 0, "tipo": 1}
    contas = [  # conta 86751: dois orçamentos do mesmo paciente + itens sem orçamento
        {**base, "id_admissao": 31203, "id_paciente": 5, "id_orcamento": 247687, "faturamento_grupo": 24467.55},
        {**base, "id_admissao": 31203, "id_paciente": 5, "id_orcamento": 247688, "faturamento_grupo": 18510.95},
        {**base, "id_admissao": 31203, "id_paciente": 5, "id_orcamento": None, "faturamento_grupo": 40},
        {**base, "id_admissao": 40000, "id_paciente": 6, "id_orcamento": 300, "faturamento_grupo": 900,
         "pre_auditoria": 50},
    ]
    orcs = {247687: {"orcado": 20925.35, "situacao_orcamento": "Autorizado (operadora)",
                     "orcamento_inicio": datetime.datetime(2026, 8, 1), "orcamento_fim": datetime.datetime(2026, 8, 13)},
            247688: {"orcado": 17482.15, "situacao_orcamento": "Autorizado (operadora)",
                     "orcamento_inicio": datetime.datetime(2026, 8, 14), "orcamento_fim": datetime.datetime(2026, 8, 25)},
            300: {"orcado": 1000, "situacao_orcamento": "Liberado", "orcamento_inicio": None, "orcamento_fim": None}}
    g = {"glosa": 80, "recuperado": 30, "perda": 10, "faturado_planilha": 900, "motivos": "1705",
         "status_glosa": "PAGO", "situacao_cruzamento": "CONCILIADO"}
    l = conta_paciente.juntar(contas, orcs, {(86751, "A", 31203): g, (86751, "P", 6): {**g, "glosa": 7}})
    assert [x["orcado"] for x in l] == [20925.35, 17482.15, None, 1000]
    assert l[0]["orcamento_rotulo"] == "01/08 a 13/08 · Autorizado (operadora)"
    assert l[2]["orcamento_rotulo"] == "itens sem orçamento"
    # glosa da admissão só na primeira linha dela, com a nota; a do paciente 6 casou pelo total
    assert [x["glosa"] for x in l] == [80, None, None, 7]
    assert l[0]["glosa_nota"] == "(planilha) do paciente na conta (todos os orçamentos)"
    assert l[3]["glosa_nota"] == "(planilha) 1705"
    assert l[0]["orcamentos_na_conta"] == 2 and l[3]["orcamentos_na_conta"] == 1
    kpis = conta_paciente.resumo(l)
    assert round(kpis[0]["valor"], 2) == 39407.5 and kpis[4]["valor"] == 87
    passa = lambda i, **f: conta_paciente._passa(l[i], f)  # noqa: E731
    assert passa(2, orcamento="sem") and not passa(0, orcamento="sem")
    assert passa(0, orcamento="Autorizado (operadora)") and not passa(3, orcamento="Autorizado (operadora)")
    assert passa(1, destaque="varios") and not passa(3, destaque="varios")
    assert passa(3, pre="com") and passa(0, pre="sem") and not passa(0, pre="com")
    assert passa(0, desconto="sem") and not passa(0, desconto="com")
    # glosa e desfecho são do paciente na conta: a 2ª linha do paciente (sem glosa exibida) também passa
    assert l[1]["glosa"] is None and passa(1, glosa="com") and passa(1, desfecho="ambos")
    assert not passa(1, glosa="sem") and not passa(1, desfecho="aberto")


def test_faturas_agrupa_as_linhas_da_conta_do_paciente():
    from src.consultas import conta_paciente, faturas

    base = {"id_conta": 86751, "competencia": datetime.date(2026, 8, 1), "pre_auditoria": 0, "tipo": 1,
            "situacao": "Liberada (não exportada)", "bruto": 100, "pacote": 10, "faturamento_grupo": 90,
            "fatura_operadora": 90, "desconto_informativo": 0}
    contas = [{**base, "id_admissao": 31203, "id_paciente": 5, "id_orcamento": 247687},
              {**base, "id_admissao": 31203, "id_paciente": 5, "id_orcamento": 247688, "pre_auditoria": 4},
              {**base, "id_admissao": 31300, "id_paciente": 7, "id_orcamento": 247687}]  # orçamento repetido
    orcs = {247687: {"orcado": 200, "situacao_orcamento": "Liberado", "orcamento_inicio": None, "orcamento_fim": None},
            247688: {"orcado": 50, "situacao_orcamento": "Liberado", "orcamento_inicio": None, "orcamento_fim": None}}
    g = {"glosa": 30, "recuperado": 10, "perda": 0, "faturado_planilha": 90, "motivos": "1705", "status_glosa": "PAGO",
         "situacao_cruzamento": "CONCILIADO", "notas_planilha": "4655"}
    linhas = conta_paciente.juntar(contas, orcs, {(86751, "A", 31203): g})
    assert all(l["nota_fiscal"] == "4655" and l["nf_origem"] == "planilha" for l in linhas)
    [f] = faturas.agrupar(linhas)
    assert f["pacientes"] == 2 and f["orcamentos"] == 2 and f["orcado"] == 250  # orçamento distinto conta uma vez
    assert f["faturamento_grupo"] == 270 and f["pre_auditoria"] == 4 and f["glosa"] == 30
    assert f["detalhe"] == "/consultas/conta-paciente?mes=2026-08&busca=86751"
    assert faturas._passa(f, {"glosa": "com", "desfecho": "recuperado", "pre": "com"})
    assert not faturas._passa(f, {"desfecho": "perda"})


def test_nota_fiscal_prefere_erp():
    from src.consultas import conta_paciente

    assert conta_paciente.nota_fiscal({"nf_numero": "258", "nf_serie": "1"}, {"999"}) == ("258 / série 1", "ERP")
    assert conta_paciente.nota_fiscal({"doc_financeiro": "01070"}, None) == ("1070", "ERP (doc. financeiro)")
    assert conta_paciente.nota_fiscal({"doc_financeiro": "Posterior"}, {"21"}) == ("21", "planilha")
    assert conta_paciente.nota_fiscal({"doc_financeiro": "0"}, None) == (None, None)


def test_rotulo_de_origem_da_glosa():
    from src.consultas import conta_paciente, registro

    assert registro.rotulo_origem("xml") == "(xml)" and registro.rotulo_origem(None) == "(planilha)"
    assert registro.rotulo_origem("planilha/xml") == "(xml/planilha)"
    assert conta_paciente._rotulo_origem({"origem_glosa": "xml"}) == "(xml)"
    l = registro.com_origem({"origem_glosa": "xml", "motivo": "1714", "motivo_planilha": "1705",
                             "motivo_descricao": "VALOR DO SERVIÇO SUPERIOR"})
    assert l["origem_rotulo"] == "(xml)" and l["motivo_nota"] == "Valor do serviço superior · planilha dizia 1705"
