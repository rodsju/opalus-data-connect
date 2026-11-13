"""Peças comuns aos blocos de Medicamentos (bloco_med_*)."""

import datetime

from . import comum, fonte

MESES = 12
# Foto de estoque mais velha que isso (em relação ao fim do período) ganha alerta
ESTOQUE_VELHO_DIAS = 3

REGRA_CUSTO = (
    "MATMATERIALMOV, custo do movimento (QUANTITY × UNITCOST; TOTALCOST vem nulo nas dispensações). "
    "Soma MOVTYPE 14 (dispensação da prescrição) e 11 (ressuprimento do home care) com DELIVERED > 0 e "
    "abate o 15 (devolução do paciente). Cancelados (31) e baixa sem custo (30) ficam de fora. Data = MOVDATE."
)
REGRA_RECORTE = (
    "Unidade pela admissão (IDADMISSIONDEST, ou IDADMISSIONSOURCE na devolução) → GLBHEALTHPROVDEP → "
    "GLBHEALTHPROVIDER; tipo por CAPADMISSION.ADMISSIONTYPE; categoria por SCMATERIAL → SCCCODE.IDTABLE "
    "(55 Medicamentos, 56 Mat. Enfermagem, 71 Dietas)."
)
REGRA_ESTOQUE = (
    "MATBALANCEHISTORY: foto diária do saldo por área de dispensação, valorizada por BALANCE × COST, na "
    "última data antes do fim do período. A área vira unidade pelo provider que mais recebeu dispensação "
    "dela nos 90 dias anteriores. O tipo de atendimento não se aplica ao estoque."
)


def dias(filtros):
    """Dias do período (para consumo médio diário). Sem período, None."""
    if not filtros or not filtros.inicio:
        return None
    fim = min(filtros.fim, datetime.date.today() + datetime.timedelta(days=1))
    return max((fim - filtros.inicio).days, 1)


def evolucao(filtros):
    """Custo por mês nos MESES meses que terminam no período. Guardado na memória da página."""
    chave = ("med_por_mes", "evolucao")
    if chave not in filtros._memo:
        inicio = filtros.inicio.replace(day=1)
        for _ in range(MESES - 1):
            inicio = (inicio - datetime.timedelta(days=1)).replace(day=1)
        filtros._memo[chave] = fonte.rodar("med_por_mes", {**filtros.params(), "DT_INI": inicio})
    return filtros._memo[chave]


def estoque_areas(filtros):
    """Saldo por área; None quando a consulta falha (o custo não depende dele)."""
    try:
        return filtros.rodar("med_estoque_areas")
    except comum.ConsultaFalhou:
        return None


def posicao(linhas):
    """Data da foto de estoque das linhas (date) ou None."""
    datas = [l.get("posicao") for l in linhas or [] if l.get("posicao")]
    if not datas:
        return None
    dt = max(datas)
    return dt.date() if isinstance(dt, datetime.datetime) else dt


def estoque_velho(data, filtros):
    if not data or not filtros or not filtros.fim:
        return False
    referencia = min(filtros.fim, datetime.date.today() + datetime.timedelta(days=1))
    return (referencia - data).days > ESTOQUE_VELHO_DIAS + 1


def cobertura(saldo, consumo, n_dias):
    """Dias de estoque ao ritmo do período: saldo ÷ consumo médio diário. None sem consumo."""
    saldo, consumo = comum.num(saldo), comum.num(consumo)
    if not n_dias or consumo <= 0:
        return None
    return saldo / (consumo / n_dias)
