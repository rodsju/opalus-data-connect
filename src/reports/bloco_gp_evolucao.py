"""Glosa, recurso e recuperação por competência."""

import datetime

from . import comum, gp_comum

TITULO = "Evolução por competência"
ICONE = "chart-column"
PARTIAL = "reports/bloco_gp_evolucao.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "evolucao", "titulo": "Evolução",
     "negocio": "Glosa, recursado e recuperado mês a mês, com a taxa de glosa. Mostra todas as competências "
     "mesmo com um mês filtrado. Meses recentes ainda não tiveram tempo de recurso.",
     "tecnico": "gp_por_competencia sem o filtro de período; competência = mês da data final do PERIODO ATENDIMENTO."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_competencia", com_periodo=False))


def montar(linhas):
    linhas = gp_comum.normalizar(linhas)
    rotulos = [gp_comum.competencia_rotulo(l["competencia"]) for l in linhas]
    return {
        "vazio": not linhas,
        "grafico": comum.grafico("barras-linha", rotulos, [
            {"nome": "Glosa", "tom": "coral", "valores": [l["glosa"] for l in linhas]},
            {"nome": "Recursado", "tom": "blue", "valores": [l["recursado"] for l in linhas]},
            {"nome": "Recuperado", "tom": "teal", "valores": [l["recuperado_bruto"] for l in linhas]},
            {"nome": "Taxa de glosa", "tom": "violet", "tipo": "linha", "eixo": "pct",
             "valores": [l["taxa_glosa"] or 0 for l in linhas]},
        ]),
        "linhas": linhas,
        "rotulos": rotulos,
    }


def montar_amostra():
    base = datetime.date(2025, 7, 1)
    linhas = []
    for i, (g, r, b) in enumerate([(132, 98, 29), (240, 201, 81), (902, 766, 483), (1338, 1151, 729),
                                   (1004, 853, 471), (1392, 1221, 664), (1202, 1084, 690), (666, 557, 323),
                                   (772, 676, 272), (985, 876, 56), (1047, 913, 55), (529, 306, 0)]):
        mes = (base.replace(day=28) + datetime.timedelta(days=31 * i)).replace(day=1)
        linhas.append({"competencia": mes, **gp_comum.amostra_somas(300, g * 4700, g * 1000, r * 1000, 60_000,
                                                                     b * 1000, 20_000)})
    return montar(linhas)
