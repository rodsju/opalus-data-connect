"""Backend BigQuery dos /reports: SQL em GoogleSQL, dataset vindo do ambiente,
parâmetros tipados e falha clara para o que ainda não foi migrado. Sem rede: o
client do BigQuery é substituído."""

import datetime
import re

import pytest

from src.reports import fonte, fonte_bq, sql_bq, sql_oracle

BINDS_CONHECIDOS = set(fonte_bq.TIPOS_BIND)


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("BQ_PROJECT", "projeto-teste-1")
    monkeypatch.setenv("BQ_DATASET", "bronze_x")
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    monkeypatch.setenv("REPORTS_FONTE", "bq")


@pytest.fixture
def client_falso(monkeypatch, ambiente):
    chamadas = []

    class Job:
        def __init__(self, linhas):
            self._linhas = linhas

        def result(self, timeout=None):
            return self._linhas

    class Client:
        def query(self, sql, job_config=None):
            chamadas.append((sql, job_config))
            return Job([{"UNIDADE": "A", "BRUTO": 1}])

    monkeypatch.setattr(fonte_bq, "_cliente_para", lambda cfg: Client())
    return chamadas


# --------------------------------------------------------------------------
# SQL
# --------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(sql_bq.CONSULTAS))
def test_sql_bq_e_googlesql(nome):
    sql = sql_bq.CONSULTAS[nome]
    assert set(re.findall(r"@([A-Z_]+)", sql)) <= BINDS_CONHECIDOS
    # Nada de Oracle: bind :X, NVL, TO_CHAR, ROWNUM, SYSDATE
    assert not re.search(r"(?<![:\w]):[A-Z_]+\b", sql)
    for oracle in ("NVL(", "TO_CHAR(", "ROWNUM", "SYSDATE", "DUAL", "CONNECT BY"):
        assert oracle not in sql.upper()
    # Fragmento esquecido sem interpolar: só {ds} pode sobrar
    assert "{" not in sql.replace("{ds}", "")


@pytest.mark.parametrize("nome", sorted(sql_bq.CONSULTAS))
def test_tabelas_sempre_pelo_dataset(nome):
    # Tabela sem {ds} iria para o dataset default do job, que não existe
    sql = sql_bq.CONSULTAS[nome]
    for tabela in re.findall(r"\b(?:FROM|JOIN)\s+([^\s(]+)", sql):
        assert tabela.startswith("{ds}.") or tabela.islower(), f"{nome}: {tabela} sem {{ds}}"


def test_chaves_existem_no_oracle():
    # Mesmo contrato: nenhuma chave nova sem par no Oracle durante a migração
    assert set(sql_bq.CONSULTAS) <= set(sql_oracle.CONSULTAS)


def test_faturamento_usa_a_cascata_da_conta():
    for nome in ("contas_por_status", "faturamento_por_operadora", "glosa_por_unidade", "cascata_por_pagador"):
        sql = sql_bq.CONSULTAS[nome]
        assert "i.QUANTITY - IFNULL(i.COVERAGEQUANTITY, 0)" in sql
        assert "op.CORPORATION" in sql


def test_exportadas_sem_particular():
    assert "NOT (IFNULL(op.CORPORATION, 0) = 1)" in sql_bq.CONSULTAS["exportadas_por_guia"]


# --------------------------------------------------------------------------
# Backend
# --------------------------------------------------------------------------


def test_dataset_vem_do_ambiente(client_falso, monkeypatch):
    fonte_bq.rodar("unidades_faturam", {})
    assert "`projeto-teste-1.bronze_x`.GLBENTERPRISE" in client_falso[-1][0]

    monkeypatch.setenv("BQ_DATASET", "outra_camada")
    fonte_bq.rodar("unidades_faturam", {})
    assert "`projeto-teste-1.outra_camada`.GLBENTERPRISE" in client_falso[-1][0]
    assert "{ds}" not in client_falso[-1][0]


def test_linhas_com_chaves_minusculas(client_falso):
    assert fonte_bq.rodar("unidades_faturam", {}) == [{"unidade": "A", "bruto": 1}]


def test_parametros_tipados_e_so_os_usados(client_falso):
    fonte_bq.rodar("cascata_por_pagador", {
        "DT_INI": datetime.date(2026, 10, 1), "DT_FIM": datetime.date(2026, 11, 1),
        "UNIDADE": None, "TIPO": None, "CATEGORIA": 55,
    })
    params = {p.name: p for p in client_falso[-1][1].query_parameters}
    assert set(params) == {"DT_INI", "DT_FIM", "UNIDADE", "TIPO"}  # CATEGORIA não está na SQL
    assert params["DT_INI"].type_ == "DATETIME"
    assert params["DT_INI"].value == datetime.datetime(2026, 10, 1)
    assert params["UNIDADE"].type_ == "STRING" and params["UNIDADE"].value is None
    assert params["TIPO"].type_ == "INT64" and params["TIPO"].value is None


def test_lista_vira_array():
    sql = "SELECT 1 FROM t WHERE id IN UNNEST(@IDS)"
    (param,) = fonte_bq.parametros(sql, {"IDS": [1, 2, 3]})
    assert param.array_type == "INT64" and param.values == [1, 2, 3]


def test_limite_no_fim(client_falso):
    fonte_bq.rodar("unidades_faturam", {}, limite=10)
    sql, config = client_falso[-1]
    assert sql.rstrip().endswith("LIMIT @LIMITE_REPORTS")
    assert {p.name: p.value for p in config.query_parameters}["LIMITE_REPORTS"] == 10


def test_consulta_nao_migrada_falha_claro(ambiente):
    nao_migrada = next(n for n in sql_oracle.CONSULTAS if n not in sql_bq.CONSULTAS)
    with pytest.raises(fonte.ConsultaFalhou) as falha:
        fonte.rodar(nao_migrada, {})
    assert "ainda não migrada" in falha.value.motivo


def test_sem_configuracao_e_sem_conexao(monkeypatch):
    monkeypatch.setenv("REPORTS_FONTE", "bq")
    monkeypatch.delenv("BQ_PROJECT", raising=False)
    monkeypatch.delenv("BQ_DATASET", raising=False)
    with pytest.raises(fonte.ConsultaFalhou) as falha:
        fonte.rodar("unidades_faturam", {})
    assert falha.value.sem_conexao
    assert "BQ_PROJECT" in falha.value.dica


@pytest.mark.parametrize("dataset", ["bronze; DROP", "a.b", "`x`"])
def test_dataset_invalido(monkeypatch, ambiente, dataset):
    monkeypatch.setenv("BQ_DATASET", dataset)
    with pytest.raises(fonte_bq.BqIndisponivel):
        fonte_bq._config()
