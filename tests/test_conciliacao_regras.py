"""As fórmulas da planilha base_glosa.xlsx, reproduzidas em src/conciliacao/regras.py.

Os casos saíram de linhas reais da planilha (valores, não nomes): o esperado é o
que o próprio Excel gravou na coluna de fórmula.
"""

import datetime
import pathlib
import sys
from decimal import Decimal as D

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.conciliacao import regras  # noqa: E402

HOJE = datetime.date(2026, 9, 18)  # célula W2 da planilha de set/2026
d = datetime.date

PREMISSAS = regras.Premissas.de_linhas(
    de_para=[{"empresa": "PLENO SAUDE", "convenio": "AMIL", "convenio_formula": "AMIL"},
             {"empresa": "GERIATRICS", "convenio": "CASSI", "convenio_formula": "CASSI GRT"}],
    imposto=[{"empresa": "PLENO SAUDE", "convenio": "AMIL", "imposto": D("0.0815")},
             {"empresa": "PLENO SAUDE", "convenio": "MUTUA", "imposto": D("0"),
              "data_alt1": d(2026, 4, 1), "imposto_alt1": D("0.0615")}],
    prazo=[{"convenio": "AMIL", "prazo": 31}, {"convenio": "CASSI GRT", "prazo": 46}],
    recurso=[{"convenio": "AMIL", "prazo_recurso": 90}],
    aging=[{"dia": 1, "grupo": "Até 30 dias"}, {"dia": 31, "grupo": "De 31 a 60 dias"},
           {"dia": 361, "grupo": "Acima de 360 dias"}],
)


def test_convenio_formula_pelo_de_para_e_n_quando_falta():
    assert regras.convenio_formula("pleno saude", "Amil ", PREMISSAS) == "AMIL"
    assert regras.convenio_formula("PLENO SAUDE", "INEXISTENTE", PREMISSAS) == "N"


@pytest.mark.parametrize("periodo,esperado", [
    ("01/10/2025 a 31/10/2025", d(2025, 10, 1)),
    ("02/08/2025 a 06/08/2025", d(2025, 8, 1)),
    ("01/12/25 a 31/12/25", d(2025, 12, 1)),
    ("sem data", None),
])
def test_competencia_e_o_mes_da_data_final(periodo, esperado):
    assert regras.competencia(periodo) == esperado


def test_valor_liquido_da_linha_real():
    # PLENO SAUDE / AMIL: faturado 854,63 -> líquido 784,98 na planilha
    imposto = regras.aliquota("PLENO SAUDE", "AMIL", PREMISSAS)
    assert regras.liquido(D("854.63"), imposto) == D("784.98")
    # BASE CALCULO 2 = (faturado − glosa) × (1 − imposto): 854,62 -> 784,97
    assert regras.liquido(D("854.62"), imposto) == D("784.97")


def test_aliquota_ignora_data_alt_como_a_planilha():
    assert regras.aliquota("PLENO SAUDE", "MUTUA", PREMISSAS, d(2026, 6, 1)) == 0
    assert regras.aliquota("PLENO SAUDE", "MUTUA", PREMISSAS, d(2026, 6, 1), usar_alternativas=True) == D("0.0615")
    assert regras.aliquota("PLENO SAUDE", "MUTUA", PREMISSAS, d(2026, 3, 1), usar_alternativas=True) == 0
    assert regras.aliquota("X", "Y", PREMISSAS) is None


def _linha(**campos):
    base = {"data_contratual": d(2026, 1, 10), "data_recebimento": None, "data_reapresentacao": None,
            "devolucao": None, "prazo": 31, "valor_recebido": None}
    return {**base, **campos}


@pytest.mark.parametrize("linha,esperado", [
    (_linha(data_contratual=d(2026, 10, 1)), "A VENCER"),                       # no prazo, não recebeu
    (_linha(data_contratual=d(2026, 10, 1), data_recebimento=d(2026, 9, 1)), "RECEBIDO"),
    (_linha(), "EM ATRASO"),                                                     # venceu e não recebeu
    (_linha(data_recebimento=d(2026, 1, 12)), "RECEBIDO"),
    (_linha(devolucao=d(2026, 9, 1)), "A VENCER"),                               # devolvida: 01/09 + 31 > hoje
    (_linha(devolucao=d(2026, 7, 1)), "EM ATRASO"),
    (_linha(data_reapresentacao=d(2026, 9, 1), valor_recebido=D("0")), "A VENCER"),
    (_linha(data_reapresentacao=d(2026, 6, 1), valor_recebido=D("0")), "EM ATRASO"),
    (_linha(data_reapresentacao=d(2026, 6, 1), data_recebimento=d(2026, 7, 1)), "RECEBIDO"),
    (_linha(data_contratual=None), "EM ATRASO"),                                 # Excel: 0 + prazo < hoje
])
def test_status_segue_a_switch_da_planilha(linha, esperado):
    assert regras.status_recebimento(linha, HOJE) == esperado


def test_dias_de_atraso_e_aging():
    linha = _linha(data_contratual=d(2026, 8, 1))
    assert regras.dias_atraso(linha, "EM ATRASO", HOJE) == 48
    assert regras.dias_atraso(linha, "RECEBIDO", HOJE) is None
    reap = _linha(data_reapresentacao=d(2026, 7, 1))  # conta do prazo da reapresentação
    assert regras.dias_atraso(reap, "EM ATRASO", HOJE) == (HOJE - d(2026, 8, 1)).days
    assert regras.faixa_aging(0, PREMISSAS) is None
    assert regras.faixa_aging(1, PREMISSAS) == "Até 30 dias"
    assert regras.faixa_aging(30, PREMISSAS) == "Até 30 dias"
    assert regras.faixa_aging(31, PREMISSAS) == "De 31 a 60 dias"
    assert regras.faixa_aging(400, PREMISSAS) == "Acima de 360 dias"


@pytest.mark.parametrize("campos,esperado", [
    ({"glosa": D("100")}, "ANÁLISE OPALUS"),
    ({"glosa": D("100"), "valor_recursado": D("100")}, "ANÁLISE OPERADORA"),
    ({"glosa": D("100"), "glosa_acatada": D("100")}, "ACATADO"),
    ({"glosa": D("100"), "valor_recursado": D("60"), "glosa_acatada": D("40")}, "ACATADO / ANÁLISE OPERADORA"),
    ({"glosa": D("100"), "valor_recursado": D("100"), "data_receb_recurso": d(2026, 5, 1),
      "valor_recurso_liquido": D("94")}, "PAGO"),
    ({"glosa": D("100"), "valor_recursado": D("100"), "data_receb_recurso": d(2026, 5, 1),
      "glosa_mantida": D("100")}, "GLOSA MANTIDA"),
    ({"glosa": D("0")}, None),
])
def test_status_da_glosa(campos, esperado):
    assert regras.status_glosa(campos) == esperado


def test_prazo_de_recurso_pelo_convenio_digitado():
    linha = {"convenio": "AMIL", "data_recebimento": d(2025, 12, 19)}
    assert regras.prazo_recurso(linha, "ACATADO", PREMISSAS) == d(2026, 3, 19)
    assert regras.prazo_recurso(linha, None, PREMISSAS) is None
    assert regras.prazo_recurso({**linha, "convenio": "SEM CADASTRO"}, "ACATADO", PREMISSAS) is None


@pytest.mark.parametrize("bruta,canonica", [
    ("OPERAODRA", "OPERADORA"), ("SISTEMA ", "SISTEMA"), ("FATURA,MENTO", "FATURAMENTO"),
    ("CAPTAÇÃO", "CAPTAÇÃO"), ("0", None), (None, None), ("NOVA", "NOVA"),
])
def test_normalizar_classificacao(bruta, canonica):
    assert regras.normalizar_classificacao(bruta) == canonica


def test_calcular_linha_inteira_e_divergencias():
    linha = {"empresa": "PLENO SAUDE", "convenio": "AMIL", "periodo": "01/10/2025 a 31/10/2025",
             "valor_faturado": D("854.63"), "glosa": D("0.01"), "data_entrega": d(2025, 11, 18),
             "data_recebimento": d(2025, 12, 19), "glosa_acatada": D("0.01"),
             "status_planilha": "RECEBIDO", "valor_liquido_planilha": D("784.98"), "prazo_planilha": 31,
             "status_glosa_planilha": "ACATADO", "classificacao_bruta": "SISTEMA "}
    saida, pendencias = regras.calcular(linha, PREMISSAS, HOJE)
    assert saida["convenio_formula"] == "AMIL" and saida["prazo"] == 31
    assert saida["data_contratual"] == d(2025, 12, 19)
    assert saida["status"] == "RECEBIDO" and saida["status_glosa"] == "ACATADO"
    assert saida["classificacao"] == "SISTEMA"
    assert pendencias == []
    assert regras.divergencias(saida) == []


def test_convenio_formula_digitado_prevalece():
    linha = {"empresa": "PLENO SAUDE", "convenio": "AMIL", "periodo": "01/05/2026 a 31/05/2026",
             "valor_faturado": D("100"), "glosa": D("10"), "convenio_formula_planilha": "AMIL SP"}
    saida, pendencias = regras.calcular(linha, PREMISSAS, HOJE)
    assert saida["convenio_formula"] == "AMIL SP"
    assert saida["convenio_formula_manual"] is True
    assert "sem prazo de recebimento" in pendencias  # AMIL SP não está no prazo


def test_data_1900_da_planilha_conta_como_vazia():
    saida = {"data_contratual": None, "data_contratual_planilha": d(1900, 2, 28)}
    assert "data_contratual" not in regras.divergencias(saida)


def test_premissa_formulario_converte_e_valida():
    import decimal

    import pytest

    from src.conciliacao import premissas

    r = premissas.ler_formulario("imposto", {"empresa": "GERIATRICS", "convenio": "AMIL", "imposto": "6,15",
                                             "data_alt1": "2026-10-01", "imposto_alt1": "7"})
    assert r["imposto"] == decimal.Decimal("0.0615") and r["imposto_alt1"] == decimal.Decimal("0.07")
    assert str(r["data_alt1"]) == "2026-10-01" and r["imposto_alt2"] is None
    assert premissas.ler_formulario("leitos", {"unidade": "Premier Barra HSP", "tipo_atendimento": "0",
                                               "leitos": "46", "vigente_desde": "2026-10-01"})["leitos"] == 46
    with pytest.raises(premissas.PremissaInvalida, match="imposto"):
        premissas.ler_formulario("imposto", {"empresa": "G", "convenio": "A", "imposto": "seis"})
    with pytest.raises(premissas.PremissaInvalida, match="obrigatório"):
        premissas.ler_formulario("prazo", {"convenio": " ", "prazo": "30"})
    with pytest.raises(premissas.PremissaInvalida, match="não é editável"):
        premissas.ler_formulario("motivo_tiss", {"codigo": "1"})
    assert "motivo_tiss" not in premissas.EDITAVEIS and len(premissas.EDITAVEIS) == len(premissas.TIPOS) - 1
