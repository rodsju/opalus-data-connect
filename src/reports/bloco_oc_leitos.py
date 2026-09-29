"""Distribuição dos leitos entre as unidades."""

from . import comum, oc_comum
from .bloco_oc_resumo import AMOSTRA_LEITOS

TITULO = "Leitos por unidade"
ICONE = "bed-double"
PARTIAL = "reports/bloco_oc_leitos.html"
LARGURA = "meia"
TONS = ["violet", "magenta", "coral", "green", "cyan", "blue", "amber", "teal"]
ITENS = [
    {"chave": "leitos", "titulo": "Leitos",
     "negocio": "Capacidade instalada de cada unidade de transição.",
     "tecnico": "Parâmetro 'Leitos por unidade' em Conciliação › Premissas (não existe no ERP)."},
]


def consultar(filtros):
    return montar(oc_comum.leitos(filtros))


def montar(capacidade):
    linhas = sorted(capacidade.items(), key=lambda x: -x[1])
    return {
        "vazio": not linhas,
        "total": sum(n for _, n in linhas),
        "grafico": comum.grafico("rosca", [u.replace(" HSP", "") for u, _ in linhas],
                                 [{"nome": "Leitos", "tons": TONS[:len(linhas)], "valores": [n for _, n in linhas]}],
                                 formato="int"),
    }


def montar_amostra():
    return montar(AMOSTRA_LEITOS)
