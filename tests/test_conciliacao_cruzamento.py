"""Classificação do cruzamento planilha × ERP, com o ERP simulado."""

import datetime
import pathlib
import sys
from decimal import Decimal as D

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.conciliacao import cruzamento  # noqa: E402
from src.reports import fonte  # noqa: E402


def test_protocolo_valido_normaliza_como_o_erp():
    assert cruzamento.protocolo_valido(" 1529731 ") == "1529731"
    assert cruzamento.protocolo_valido("01340288") == "1340288"          # ERP grava com zero à esquerda
    assert cruzamento.protocolo_valido("330230297758-0") == "330230297758_0"
    for invalido in ("", None, "-", "0", "10", "000"):
        assert cruzamento.protocolo_valido(invalido) is None


def test_nome_tira_tratamento_e_acento():
    assert cruzamento.nome("Sra. Fulána  de Tal ") == "FULANA DE TAL"


def adm(id_, faturado, work=0, glosa=0):
    return {"id_admissao": id_, "id_conta": 7, "unidade": "U", "operadora": "O", "faturado": D(faturado),
            "work": D(work), "glosa_iw": D(glosa)}


def test_classificar_por_admissao():
    linhas = [
        {"linha": 1, "protocolo": "1111", "paciente": "Ana", "valor_faturado": D("1832.77")},
        {"linha": 2, "protocolo": "1111", "paciente": "Ana", "valor_faturado": D("1971.47")},   # outra admissão
        {"linha": 3, "protocolo": "1111", "paciente": "Bia", "valor_faturado": D("1939.46")},   # só na versão de trabalho
        {"linha": 4, "protocolo": "1111", "paciente": "Caio", "valor_faturado": D("300.00")},   # total de 2 admissões
        {"linha": 5, "protocolo": "1111", "paciente": "Duda", "valor_faturado": D("80.00")},
        {"linha": 6, "protocolo": "1111", "paciente": "Eva", "valor_faturado": D("10.00")},
        {"linha": 7, "protocolo": "9999", "paciente": "Fê", "valor_faturado": D("10.00")},
        {"linha": 8, "protocolo": "-", "paciente": "Gil", "valor_faturado": D("10.00")},
    ]
    pares = {("1111", "ANA"): [adm(10, "1971.47", glosa=5), adm(11, "1832.77")],
             ("1111", "BIA"): [adm(20, "1449.54", work="1939.46")],
             ("1111", "CAIO"): [adm(30, "100"), adm(31, "200")],
             ("1111", "DUDA"): [adm(40, "70.00")]}
    saida = {r["linha"]: r for r in cruzamento.classificar(linhas, pares, {"1111"})}
    assert (saida[1]["situacao"], saida[1]["id_admissao"]) == (cruzamento.CONCILIADO, 11)
    assert (saida[2]["situacao"], saida[2]["id_admissao"], saida[2]["glosa_iw"]) == (cruzamento.CONCILIADO, 10, 5)
    assert (saida[3]["situacao"], saida[3]["regra"]) == (cruzamento.CONCILIADO, "versão de trabalho")
    assert (saida[4]["situacao"], saida[4]["regra"]) == (cruzamento.CONCILIADO, "total do paciente")
    assert saida[5]["situacao"] == cruzamento.DIVERGENTE and saida[5]["diferenca"] == D("10.00")
    assert saida[6]["situacao"] == cruzamento.PACIENTE_NAO_ACHADO
    assert saida[7]["situacao"] == cruzamento.PROTOCOLO_NAO_ACHADO
    assert saida[8]["situacao"] == cruzamento.SEM_PROTOCOLO


def test_mesma_admissao_soma_uma_vez():
    linhas = [{"linha": 1, "protocolo": "1111", "paciente": "Ana", "valor_faturado": D("50")},
              {"linha": 2, "protocolo": "1111", "paciente": "Ana", "valor_faturado": D("60")}]
    saida = cruzamento.classificar(linhas, {("1111", "ANA"): [adm(10, "100")]}, {"1111"})
    assert [r["principal"] for r in saida] == [True, False]


def test_segunda_passada_por_paciente_e_competencia():
    comp = datetime.date(2026, 6, 1)
    linhas = [{"linha": 1, "protocolo": "224425913/225437232", "paciente": "Ana", "competencia": comp,
               "valor_faturado": D("500.00")},
              {"linha": 2, "protocolo": "0Y41", "paciente": "Bia", "competencia": comp, "valor_faturado": D("20")}]
    resultado = cruzamento.classificar(linhas, {}, set())
    por_comp = {("ANA", comp): [{**adm(10, "500.00"), "protocolo": "224425913"}],
                ("BIA", comp): [{**adm(11, "8"), "protocolo": "X"}]}
    saida = {r["linha"]: r for r in cruzamento.recasar_sem_protocolo(linhas, resultado, por_comp)}
    assert (saida[1]["situacao"], saida[1]["regra"], saida[1]["protocolo_erp"]) == (
        cruzamento.CONCILIADO, "paciente + competência", "224425913")
    assert saida[2]["situacao"] == cruzamento.SEM_PROTOCOLO   # valor não bate: fica como estava


def test_buscar_erp_agrupa_por_admissao(monkeypatch):
    def falsa(nome, params, limite=None):
        assert params["PROTOCOLOS"] == ["1111"]
        if nome == "conciliacao_protocolos":
            return [{"protocolo": "1111", "id_conta": 1, "id_admissao": 10, "unidade": "U", "operadora": "O",
                     "paciente": "Ana", "faturado": 100.1, "glosa_iw": 1},
                    {"protocolo": "1111", "id_conta": 1, "id_admissao": 11, "unidade": "U", "operadora": "O",
                     "paciente": "ANA ", "faturado": 50, "glosa_iw": 0}]
        return [{"protocolo": "1111", "id_admissao": 10, "paciente": "Ana", "faturado": 90}]

    monkeypatch.setattr(fonte, "rodar", falsa)
    pares, achados = cruzamento.buscar_erp({"1111"})
    assert achados == {"1111"}
    admissoes = {a["id_admissao"]: a for a in pares[("1111", "ANA")]}
    assert admissoes[10]["faturado"] == D("100.1") and admissoes[10]["work"] == 90
    assert admissoes[11]["faturado"] == 50


def test_lista_vira_binds_no_oracle(monkeypatch):
    from src.reports import fonte_oracle, sql_oracle

    capturado = {}

    class Cursor:
        description = [("PROTOCOLO",)]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, sql, binds):
            capturado["sql"], capturado["binds"] = sql, binds

        def fetchall(self):
            return []

    class Conexao:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(fonte_oracle, "_conectar", lambda cfg: Conexao())
    monkeypatch.setattr(fonte_oracle, "_config", lambda: {})
    monkeypatch.setitem(sql_oracle.CONSULTAS, "teste", "SELECT 1 FROM T WHERE X IN (:PROTOCOLOS)")
    fonte_oracle.rodar("teste", {"PROTOCOLOS": ["a", "b"], "UNIDADE": None})
    assert "IN (:PROTOCOLOS_0, :PROTOCOLOS_1)" in capturado["sql"]
    assert capturado["binds"] == {"PROTOCOLOS_0": "a", "PROTOCOLOS_1": "b"}
