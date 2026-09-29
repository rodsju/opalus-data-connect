"""Ocupação por unidade de hospital de transição: leitos × ocupados × taxa."""

from . import comum, oc_comum
from .bloco_oc_resumo import AMOSTRA_ATUAL, AMOSTRA_LEITOS

TITULO = "Ocupação por unidade (hospital de transição)"
ICONE = "building-2"
PARTIAL = "reports/bloco_oc_unidades.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "unidade", "titulo": "Por unidade",
     "negocio": "Leitos, ocupados e taxa de cada unidade de transição. Clique na unidade para ver os pacientes.",
     "tecnico": "Ocupados = STATUS 1 sem alta, ADMISSIONTYPE 0; leitos = parâmetro vigente."},
]


def consultar(filtros):
    return montar(oc_comum.atual(filtros), oc_comum.leitos(filtros))


def montar(atual, capacidade):
    linhas = oc_comum.por_unidade_ht(atual, capacidade)
    return {
        "vazio": not linhas,
        "linhas": linhas,
        "grafico": comum.grafico("barras-linha", [l["unidade"].replace(" HSP", "") for l in linhas], [
            {"nome": "Leitos", "tom": "blue", "valores": [l["leitos"] or 0 for l in linhas]},
            {"nome": "Ocupados", "tom": "teal", "valores": [l["ocupados"] for l in linhas]},
            {"nome": "Taxa de ocupação", "tom": "coral", "tipo": "linha", "eixo": "pct",
             "valores": [l["taxa"] or 0 for l in linhas]},
        ], formato="int"),
    }


def montar_amostra():
    return montar(AMOSTRA_ATUAL, AMOSTRA_LEITOS)
