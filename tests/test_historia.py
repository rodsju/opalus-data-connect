"""História da conta: exportado, retorno da operadora e glosa repartida entre orçamentos -- sem banco."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.consultas import historia  # noqa: E402

EXP, ABERTA = "Exportada (fechada)", "Aberta (não liberada)"


def linha(conta=1, adm=10, orc=100, fat=100.0, situacao=EXP, **kw):
    return {"id_conta": conta, "id_admissao": adm, "id_paciente": 5, "id_orcamento": orc, "situacao": situacao,
            "bruto": fat + 20, "pacote": 20, "pre_auditoria": 0, "faturamento_grupo": fat, "particular": 0,
            "fatura_operadora": fat, **kw}


def ret(glosas=None, xml=None, itens=None):
    return {"glosas": glosas or {}, "xml": xml or {}, "itens": itens or {}}


def g(glosa, **kw):
    return {"glosa": glosa, "recuperado": 0, "perda": 0, "faturado_planilha": 0, "motivos": "1705", **kw}


def test_retorno_de_cada_guia():
    l = historia.marcar([linha(conta=1), linha(conta=2), linha(conta=3), linha(conta=4, situacao=ABERTA)],
                        ret(glosas={(1, "A", 10): g(30, origem_glosa="xml")}, xml={(2, 10): {"glosa": 0}}))
    assert [(x["retorno"], x["glosa"]) for x in l] == [
        ("glosado", 30), ("sem glosa", 0), ("sem retorno", None), ("não exportado", None)]
    assert [x["exportado"] for x in l] == [100, 100, 100, 0]
    assert l[0]["glosa_nota"] == "glosado (xml) 1705"


def test_sem_conciliacao_nao_vira_sem_retorno():
    [l] = historia.marcar([linha()], None)
    assert l["retorno"] == "sem conciliação" and l["glosa"] is None


def test_glosa_da_guia_rateada_entre_orcamentos_e_fecha():
    l = historia.marcar([linha(orc=100, fat=200), linha(orc=101, fat=100)], ret(glosas={(1, "A", 10): g(100)}))
    assert [x["glosa"] for x in l] == [66.67, 33.33] and all(x["glosa_rateada"] for x in l)
    assert historia.repartir(10, [1 / 3] * 3) == [3.34, 3.33, 3.33]


def test_glosa_por_item_do_xml_e_exata():
    l = historia.marcar([linha(orc=100, fat=200), linha(orc=101, fat=100)],
                        ret(glosas={(1, "A", 10): g(40)}, itens={(1, 10, 101): 40}))
    assert [x["glosa"] for x in l] == [0, 40] and not any(x["glosa_rateada"] for x in l)


def test_glosa_casada_pelo_paciente_entra_numa_guia_so():
    l = historia.marcar([linha(adm=10), linha(adm=11)], ret(glosas={(1, "P", 5): g(50)}))
    assert [x["glosa"] for x in l] == [50, None]


def test_agregar_por_orcamento():
    linhas = historia.marcar([linha(conta=1, fat=100), linha(conta=2, fat=50, situacao=ABERTA),
                              linha(conta=3, orc=200, fat=0, situacao=ABERTA)],
                             ret(glosas={(1, "A", 10): g(10)}))
    h = historia.agregar(linhas, "id_orcamento")
    assert h[100]["faturamento_grupo"] == 150 and h[100]["exportado"] == 100 and h[100]["a_exportar"] == 50
    assert h[100]["exportado_rotulo"] == "parcial" and h[100]["retorno"] == "glosado" and h[100]["glosa"] == 10
    assert h[100]["glosado"] == "sim"
    # Conta aberta com R$ 0 (caso 223406): nada a exportar
    assert h[200]["a_exportar"] == 0 and h[200]["exportado_rotulo"] == "—"
    assert historia.rotulo_exportado(100, 100) == "sim" and historia.rotulo_exportado(100, 0) == "não"
