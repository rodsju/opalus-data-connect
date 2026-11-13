"""Medicamentos: custo mês a mês nos 12 meses que terminam no período."""

import datetime

from . import comum, med_comum

TITULO = "Evolução do custo"
ICONE = "trending-up"
PARTIAL = "reports/bloco_med_evolucao.html"
LARGURA = "meia"
ITENS = [
    {"chave": "mes", "titulo": "Custo por mês",
     "negocio": "O custo dispensado em cada um dos 12 meses até o período escolhido, com o custo por paciente "
     "para separar volume (mais pacientes) de preço (mais caro por paciente).",
     "tecnico": "Mesma regra do custo, agrupada por TO_CHAR(MOVDATE, 'YYYY-MM'). Com intervalo personalizado, "
     "os 12 meses terminam no mês da data final. " + med_comum.REGRA_CUSTO},
]


def consultar(filtros):
    return montar(med_comum.evolucao(filtros))


def montar(linhas):
    por_mes = {l["grupo"]: l for l in linhas if l.get("grupo")}
    if not por_mes:
        return {"vazio": True}
    meses = _sequencia(min(por_mes), max(por_mes))
    serie = []
    for mes in meses:
        l = por_mes.get(mes, {})
        custo, pacientes = comum.num(l.get("custo")), comum.num(l.get("pacientes"))
        ano, numero = mes.split("-")
        serie.append({"mes": mes, "rotulo": comum.rotulo_mes(datetime.date(int(ano), int(numero), 1)),
                      "custo": custo, "pacientes": int(pacientes),
                      "por_paciente": custo / pacientes if pacientes else None})
    anteriores = [s["custo"] for s in serie[:-1] if s["custo"]]
    media = sum(anteriores) / len(anteriores) if anteriores else None
    ultimo = serie[-1]
    return {
        "vazio": False,
        "serie": serie,
        "media": media,
        "variacao": comum.pct(ultimo["custo"] - media, media) if media else None,
        "grafico": comum.grafico("barras", [s["rotulo"] for s in serie], [
            {"nome": "Custo", "tom": "violet", "valores": [s["custo"] for s in serie]},
        ], gradiente=True),
    }


def _sequencia(primeiro, ultimo):
    ano, mes = map(int, primeiro.split("-"))
    fim = tuple(map(int, ultimo.split("-")))
    saida = []
    while (ano, mes) <= fim:
        saida.append(f"{ano:04d}-{mes:02d}")
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return saida


AMOSTRA = [
    {"grupo": f"{a:04d}-{m:02d}", "custo": c, "pacientes": p}
    for (a, m), c, p in zip(
        [(2025, 9), (2025, 10), (2025, 11), (2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5),
         (2026, 6), (2026, 7), (2026, 8)],
        [1.82e6, 1.91e6, 1.88e6, 2.04e6, 1.95e6, 1.79e6, 2.01e6, 2.07e6, 2.12e6, 2.05e6, 2.18e6, 2.16e6],
        [1_120, 1_150, 1_140, 1_180, 1_170, 1_130, 1_190, 1_210, 1_230, 1_220, 1_250, 1_240],
    )
]


def montar_amostra():
    return montar(AMOSTRA)
