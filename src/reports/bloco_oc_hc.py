"""Home care: pacientes ativos por unidade (sem taxa -- não há leito)."""

from . import comum, oc_comum
from .bloco_oc_resumo import AMOSTRA_ATUAL

TITULO = "Home care: pacientes ativos"
ICONE = "house"
PARTIAL = "reports/bloco_oc_hc.html"
LARGURA = "meia"
ITENS = [
    {"chave": "censo", "titulo": "Censo",
     "negocio": "Pacientes em atendimento domiciliar por unidade. Não há taxa de ocupação: home care não tem leito.",
     "tecnico": "STATUS 1 sem alta, ADMISSIONTYPE 1."},
]


def consultar(filtros):
    return montar(oc_comum.atual(filtros))


def montar(atual):
    linhas = comum.ordenar([dict(l) for l in atual if l["tipo"] == oc_comum.HC], "ocupados")
    return {
        "vazio": not linhas,
        "total": sum(int(comum.num(l["ocupados"])) for l in linhas),
        "altura": max(200, 30 * len(linhas) + 60),
        "grafico": comum.grafico("barras-h", [l["unidade"] for l in linhas],
                                 [{"nome": "Ativos", "tom": "magenta", "valores": [l["ocupados"] for l in linhas]}],
                                 formato="int"),
    }


def montar_amostra():
    return montar(AMOSTRA_ATUAL)
