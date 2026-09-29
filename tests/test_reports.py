"""Testes dos /reports que rodam sem Oracle.

Cobrem o período (fim exclusivo), os montadores puros de cada bloco, a
integridade do registro de blocos e as rotas com a fonte substituída.
"""

import datetime
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.reports import comum, fonte, relatorios, sql_oracle  # noqa: E402
from src.reports import bloco_contas_status, bloco_glosa_unidade, bloco_resumo  # noqa: E402

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "src" / "templates"


# --------------------------------------------------------------------------
# Período
# --------------------------------------------------------------------------


def test_periodo_fim_exclusivo():
    assert comum.periodo("2026-06") == (datetime.date(2026, 6, 1), datetime.date(2026, 7, 1))


def test_periodo_vira_o_ano():
    assert comum.periodo("2025-12") == (datetime.date(2025, 12, 1), datetime.date(2026, 1, 1))


@pytest.mark.parametrize("mes", ["", "2026", "2026-13", "junho", None])
def test_periodo_invalido(mes):
    with pytest.raises(comum.PeriodoInvalido):
        comum.periodo(mes)


def test_mes_padrao_e_o_anterior():
    assert comum.mes_padrao(datetime.date(2026, 1, 15)) == "2025-12"
    assert comum.mes_padrao(datetime.date(2026, 9, 28)) == "2026-08"


# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(sql_oracle.CONSULTAS))
def test_sql_so_usa_binds_conhecidos(nome):
    sql = sql_oracle.CONSULTAS[nome]
    binds = set(re.findall(r":([A-Z_]+)", sql))
    assert binds <= {"DT_INI", "DT_FIM", "UNIDADE", "PROTOCOLOS", "COMPETENCIAS", "ID", "TIPO", "IDS", "ADMISSAO",
                     "ORCAMENTO", "SENHAS"}
    # Fragmento esquecido sem interpolar viraria SQL inválida só em produção
    assert "{" not in sql


@pytest.mark.parametrize("nome", ["orcamentos_por_status", "gap_resumo"])
def test_orcamento_vale_pelos_itens(nome):
    # BUDGETCHARGE só é gravado no cancelamento: ler o cabeçalho zera os abertos
    sql = sql_oracle.CONSULTAS[nome]
    assert "CAPBUDGETITEM bi WHERE bi.IDBUDGET = b.ID" in sql
    assert "BUDGETCHARGE" not in sql and "ANALYSISCHARGE" not in sql


def test_faturamento_usa_a_cascata_da_conta():
    # A operadora recebe preço × (qtd − qtd coberta); particular = entidade do próprio grupo
    for nome in ("contas_por_status", "faturamento_por_operadora", "glosa_por_unidade", "cascata_por_pagador"):
        sql = sql_oracle.CONSULTAS[nome]
        assert "i.QUANTITY - NVL(i.COVERAGEQUANTITY, 0)" in sql
        assert "op.CORPORATION" in sql


# --------------------------------------------------------------------------
# Registro de blocos
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bloco", relatorios.BLOCOS, ids=relatorios.slug_do_bloco)
def test_bloco_cumpre_o_contrato(bloco):
    for nome in ("TITULO", "ICONE", "PARTIAL", "LARGURA", "ITENS"):
        assert getattr(bloco, nome), nome
    assert bloco.LARGURA in {"inteira", "meia", "faixa"}
    assert (TEMPLATES / bloco.PARTIAL).is_file()
    assert callable(bloco.consultar)
    dados = bloco.montar_amostra()
    assert isinstance(dados, dict) and not dados.get("vazio")


def test_slugs_sao_unicos():
    slugs = [relatorios.slug_do_bloco(b) for b in relatorios.BLOCOS]
    assert len(slugs) == len(set(slugs))


# --------------------------------------------------------------------------
# Montadores
# --------------------------------------------------------------------------


def test_resumo_tira_simulacao_do_faturado():
    contas = [
        {"situacao": "Exportada (fechada)", "contas": 2, "faturamento_grupo": 100, "fatura_operadora": 90,
         "particular": 10},
        {"situacao": "Aberta (não liberada)", "contas": 1, "faturamento_grupo": 50, "fatura_operadora": 50},
        {"situacao": "Simulação", "contas": 5, "faturamento_grupo": 999, "fatura_operadora": 999},
    ]
    cards = {c["rotulo"]: c for c in bloco_resumo.montar(contas, [], None)["cards"]}
    assert cards["Faturamento do grupo"]["valor"] == 150
    assert cards["Fatura operadora"]["valor"] == 140
    assert cards["Em aberto"]["valor"] == 50
    assert cards["Taxa de glosa"]["valor"] is None  # divisor zero não quebra
    assert "Autorizado sem faturar" not in cards  # gap ausente com filtro de unidade


def test_resumo_gap_sem_valor_mostra_quantidade():
    gap = [{"autorizados_sem_faturamento": 3, "valor_autorizado_pendente": None}]
    cards = {c["rotulo"]: c for c in bloco_resumo.montar([], [], gap)["cards"]}
    assert cards["Autorizado sem faturar"]["valor"] == 3
    assert cards["Autorizado sem faturar"]["formato"] == "int"


def test_contas_status_ordena_pelo_ciclo_e_soma():
    linhas = [
        {"unidade": "A", "situacao": "Simulação", "contas": 1, "faturamento_grupo": 10},
        {"unidade": "A", "situacao": "Exportada (fechada)", "contas": 2, "faturamento_grupo": 30},
        {"unidade": "B", "situacao": "Exportada (fechada)", "contas": 1, "faturamento_grupo": 60},
    ]
    dados = bloco_contas_status.montar(linhas)
    assert [r["situacao"] for r in dados["resumo"]] == ["Exportada (fechada)", "Simulação"]
    assert dados["total"]["valor"] == 100
    assert dados["grafico"]["rotulos"] == ["B", "A"]  # maior unidade primeiro


def test_pareto_acumula():
    linhas = [{"v": 50}, {"v": 30}, {"v": 20}]
    comum.com_participacao(linhas, "v")
    assert [round(l["pct_acum"]) for l in linhas] == [50, 80, 100]


def test_top_com_outros_soma_o_resto():
    linhas = [{"k": str(i), "v": 1.0} for i in range(5)]
    saida = comum.top_com_outros(linhas, "k", ["v"], 2)
    assert len(saida) == 3 and saida[-1]["v"] == 3 and saida[-1]["outros"]


def test_glosa_taxa_por_unidade():
    dados = bloco_glosa_unidade.montar(
        [{"unidade": "A", "itens": 10, "itens_glosados": 1, "fatura_operadora": 200, "glosa": 10,
          "glosa_sustentada": 5, "glosa_recuperada": 2}]
    )
    assert dados["linhas"][0]["taxa"] == 5
    assert dados["total"]["taxa"] == 5


# --------------------------------------------------------------------------
# Rotas
# --------------------------------------------------------------------------


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient

    from src.main import app

    return TestClient(app)


HTML = {"accept": "text/html"}


def test_galeria_sem_oracle(cliente, monkeypatch):
    def proibido(*a, **k):
        raise AssertionError("a galeria não pode consultar a fonte")

    monkeypatch.setattr(fonte, "rodar", proibido)
    r = cliente.get("/reports/blocos", headers=HTML)
    assert r.status_code == 200
    assert "Item indisponível" not in r.text
    for bloco in relatorios.BLOCOS:
        assert bloco.TITULO in r.text


def test_relatorio_com_fonte_falsa(cliente, monkeypatch):
    amostras = {
        "contas_por_status": bloco_resumo.AMOSTRA_CONTAS,
        "glosa_por_unidade": bloco_resumo.AMOSTRA_GLOSA,
        "gap_resumo": bloco_resumo.AMOSTRA_GAP,
        "unidades_faturam": [{"unidade": "Premier Brooklin"}],
    }
    chamadas = []

    def falsa(nome, params, limite=None):
        chamadas.append(nome)
        return amostras.get(nome, [])

    monkeypatch.setattr(fonte, "rodar", falsa)
    r = cliente.get("/reports/faturamento?mes=2026-06", headers=HTML)
    assert r.status_code == 200
    assert "rp-kpi" in r.text
    assert "Premier Brooklin" in r.text
    # Resumo e bloco de status leem a mesma consulta: roda uma vez só
    assert chamadas.count("contas_por_status") == 1


def test_relatorio_sem_oracle_mostra_alerta(cliente, monkeypatch):
    def fora(nome, params, limite=None):
        falha = fonte.ConsultaFalhou(nome, "não foi possível conectar", "a VPN provavelmente está fora")
        falha.sem_conexao = True
        raise falha

    monkeypatch.setattr(fonte, "rodar", fora)
    r = cliente.get("/reports/glosa-iw?mes=2026-03", headers=HTML)
    assert r.status_code == 200
    assert "Oracle indisponível" in r.text
    assert "VPN" in r.text


def test_mes_invalido_cai_no_padrao(cliente, monkeypatch):
    monkeypatch.setattr(fonte, "rodar", lambda *a, **k: [])
    r = cliente.get("/reports/faturamento?mes=lixo", headers=HTML)
    assert r.status_code == 200
    assert "Mostrando o mês padrão" in r.text


def test_relatorio_inexistente(cliente):
    assert cliente.get("/reports/nao-existe", headers=HTML).status_code == 404


def test_glosa_antiga_redireciona(cliente):
    r = cliente.get("/reports/glosa?mes=2026-03", headers=HTML, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/reports/glosa-iw?mes=2026-03"


def test_glosa_iw_avisa_que_esta_desatualizada(cliente, monkeypatch):
    monkeypatch.setattr(fonte, "rodar", lambda *a, **k: [])
    r = cliente.get("/reports/glosa-iw?mes=2026-03", headers=HTML)
    assert "jul/2025" in r.text and "Glosa (xml/planilha)" in r.text


def test_glosa_planilha_sem_carga_mostra_cta(cliente, monkeypatch):
    from src.conciliacao import banco

    monkeypatch.setattr(banco, "carga_ativa", lambda tipo="glosa": None)
    r = cliente.get("/reports/glosa-planilha", headers=HTML)
    assert r.status_code == 200
    assert "Nenhuma carga da planilha" in r.text


def test_glosa_planilha_consulta_pelo_postgres(cliente, monkeypatch):
    from src.conciliacao import banco
    from src.reports import fonte_pg

    monkeypatch.setattr(banco, "carga_ativa", lambda tipo="glosa": {"id": 7, "data_referencia": datetime.date(2026, 9, 18)})
    pedidos = []

    def falsa(nome, params, limite=None):
        pedidos.append((nome, params.get("CONVENIO")))
        return []

    monkeypatch.setattr(fonte_pg, "rodar", falsa)
    r = cliente.get("/reports/glosa-planilha?convenio=CASSI", headers=HTML)
    assert r.status_code == 200
    assert ("gp_totais", "CASSI") in pedidos
    assert "Carga #7" in r.text


def test_cascata_fecha_e_acusa_quando_nao_fecha():
    from src.reports import bloco_cascata

    ok = bloco_cascata.montar([{"bruto": 100, "pacote": 37, "pre_auditoria": 3, "faturamento_grupo": 60,
                                "particular": 10, "fatura_operadora": 50, "tributos_erp": 5}])
    assert ok["fecha"] and [p["valor"] for p in ok["passos"]] == [100, 37, 3, 60, 10, 50]
    assert ok["grafico"]["passos"] == ["total", "neg", "neg", "total", "neg", "total"]
    # sem a pré-auditoria no fechamento, os 3 somem e a cascata acusa
    quebrada = bloco_cascata.montar([{"bruto": 100, "pacote": 37, "pre_auditoria": 0, "faturamento_grupo": 60,
                                      "particular": 10, "fatura_operadora": 50, "tributos_erp": 5}])
    assert not quebrada["fecha"]


def test_cascata_da_glosa_ate_o_saldo():
    from src.reports import bloco_gp_cascata

    d = bloco_gp_cascata.montar({"linhas": 10, "sem_erp": 1, "faturado_sem_erp": 5, "fatura": 1000,
                                 "retencao": 60, "recebido": 700, "recurso": 50, "perda": 40})
    passos = {p["rotulo"]: p["valor"] for p in d["passos"]}
    assert passos["Líquido previsto"] == 940
    assert passos["Saldo a receber"] == 940 - 700 - 50 - 40
    assert bloco_gp_cascata.montar({"fatura": 0})["vazio"]


def test_reports_nao_listam_paciente_nem_protocolo():
    """Report é leitura agregada; o caso concreto (paciente, protocolo) fica em Consultas."""
    for arquivo in (TEMPLATES / "reports").glob("bloco_*.html"):
        texto = arquivo.read_text(encoding="utf-8")
        assert "paciente_codigo" not in texto and "l.protocolo" not in texto, arquivo.name


def test_ocupacao_taxa_por_unidade_e_home_care_sem_taxa():
    from src.reports import bloco_oc_resumo, bloco_oc_unidades, oc_comum

    atual = [{"unidade": "A HSP", "tipo": 0, "ocupados": 9, "permanencia_media": 10},
             {"unidade": "B HSP", "tipo": 0, "ocupados": 3, "permanencia_media": 20},
             {"unidade": "C HC", "tipo": 1, "ocupados": 100, "permanencia_media": 300}]
    linhas = {l["unidade"]: l for l in bloco_oc_unidades.montar(atual, {"A HSP": 10})["linhas"]}
    assert linhas["A HSP"]["taxa"] == 90 and linhas["A HSP"]["livres"] == 1
    assert linhas["B HSP"]["taxa"] is None          # sem leito cadastrado: fora da taxa
    cards = {c["rotulo"]: c["valor"] for c in bloco_oc_resumo.montar(atual, {"A HSP": 10})["cards"]}
    assert cards["Ocupação hospitalar"] == 90 and cards["Home care ativos"] == 100
    assert "C HC" not in {l["unidade"] for l in oc_comum.por_unidade_ht(atual, {"A HSP": 10})}


def test_leitos_respeitam_filtro_de_unidade_e_tipo(monkeypatch):
    from src.reports import comum as comum_, oc_comum

    monkeypatch.setattr(fonte, "rodar", lambda nome, p, limite=None: [
        {"unidade": "A HSP", "tipo_atendimento": 0, "leitos": 10}, {"unidade": "B HSP", "tipo_atendimento": 0, "leitos": 5}])
    assert oc_comum.leitos(comum_.Filtros("2026-06", "a hsp")) == {"A HSP": 10}
    assert oc_comum.leitos(comum_.Filtros("2026-06", tipo="1")) == {}
    assert oc_comum.leitos(comum_.Filtros("2026-06")) == {"A HSP": 10, "B HSP": 5}


def test_pre_auditoria_bloco_e_consulta():
    from src.consultas import registro
    from src.reports import bloco_pre_auditoria

    d = bloco_pre_auditoria.montar_amostra()
    assert d["kpis"][0]["valor"] == 27_700 and round(d["kpis"][2]["valor"], 1) == round(27 / 28 * 100, 1)
    assert d["motivos"][0]["origem"] == "interno" and d["grafico_meses"]["rotulos"][0] == "2026-01"
    consulta = registro.CONSULTAS["pre-auditoria"]
    nome = [c for c in consulta["colunas"] if c.get("formato") == "nome_paciente"]
    assert nome and nome[0]["so_tela"]  # nome nunca no CSV
