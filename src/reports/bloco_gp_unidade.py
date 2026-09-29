"""Glosa por empresa e filial."""

from . import comum, gp_comum

TITULO = "Glosa por empresa e filial"
ICONE = "building"
PARTIAL = "reports/bloco_gp_unidade.html"
LARGURA = "meia"
ITENS = [
    {"chave": "unidade", "titulo": "Empresa e filial",
     "negocio": "Onde a glosa se concentra entre as empresas do grupo e as filiais da Pleno.",
     "tecnico": "gp_por_unidade: EMPRESA + FILIAL da planilha (não é a unidade do ERP)."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_unidade"))


def montar(linhas):
    linhas = comum.ordenar(gp_comum.normalizar(linhas), "glosa")
    total = comum.com_participacao(linhas, "glosa")
    return {"vazio": not linhas, "linhas": linhas, "total": {"glosa": total}}


def montar_amostra():
    return montar([
        {"empresa": e, "filial": f, **gp_comum.amostra_somas(n, g * 5, g, g * 0.8, 0, g * 0.35, 0)}
        for e, f, n, g in [("PLENO SAUDE", "RJ", 1786, 3_900_000), ("GERIATRICS", "GERIATRICS HC", 1053, 2_200_000),
                           ("PLENO SAUDE", "BSB", 913, 1_700_000), ("PLENO SAUDE", "SP", 852, 1_500_000),
                           ("PREMIER BROOKLIN", "PREMIER BROOKLIN", 102, 700_000)]
    ])
