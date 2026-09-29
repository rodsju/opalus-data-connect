"""Glosa por convênio: quem mais glosa e quanto se recupera de cada um."""

from . import comum, gp_comum

TITULO = "Glosa por convênio"
ICONE = "building-2"
PARTIAL = "reports/bloco_gp_convenio.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "convenio", "titulo": "Convênio",
     "negocio": "Concentração da glosa por operadora, com taxa de glosa e de recuperação de cada uma.",
     "tecnico": "gp_por_convenio: CONVENIO digitado na planilha (não o convênio fórmula)."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_convenio"))


def montar(linhas):
    linhas = comum.ordenar(gp_comum.normalizar(linhas), "glosa")
    total = comum.com_participacao(linhas, "glosa")
    topo = linhas[:10]
    return {
        "vazio": not linhas,
        "grafico": comum.grafico("barras-h", [l["convenio"] for l in topo], [
            {"nome": "Recuperado", "tom": "teal", "valores": [l["recuperado_bruto"] for l in topo]},
            {"nome": "Perda", "tom": "magenta", "valores": [l["acatada"] + l["mantida"] for l in topo]},
            {"nome": "Em aberto", "tom": "amber",
             "valores": [max(l["glosa"] - l["recuperado_bruto"] - l["acatada"] - l["mantida"], 0) for l in topo]},
        ], empilhado=True),
        "altura": max(240, 34 * len(topo) + 60),
        "linhas": comum.top_com_outros(linhas, "convenio", gp_comum.SOMAS + ["pct"], 15),
        "total": {"glosa": total, "linhas": sum(l["linhas"] for l in linhas),
                  "recursado": sum(l["recursado"] for l in linhas),
                  "recuperado_bruto": sum(l["recuperado_bruto"] for l in linhas)},
    }


def montar_amostra():
    return montar([
        {"convenio": c, **gp_comum.amostra_somas(n, g * 5, g, g * 0.85, g * 0.1, g * r, g * 0.05)}
        for c, n, g, r in [("CASSI", 1313, 2_900_000, 0.42), ("BRADESCO SAUDE", 1279, 2_400_000, 0.35),
                           ("REAL GRANDEZA", 738, 1_300_000, 0.30), ("AMIL", 310, 820_000, 0.22),
                           ("CAPESESP", 220, 610_000, 0.40), ("MEDISERVICE", 140, 330_000, 0.18)]
    ])
