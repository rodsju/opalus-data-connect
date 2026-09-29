"""Origem da glosa: cadastro, operadora, sistema, faturamento..."""

from . import comum, gp_comum

TITULO = "Origem da glosa"
ICONE = "tags"
PARTIAL = "reports/bloco_gp_classificacao.html"
LARGURA = "meia"
TONS = ["coral", "blue", "violet", "amber", "teal", "magenta", "cyan", "green", "navy", "neutral"]
ITENS = [
    {"chave": "classificacao", "titulo": "Classificação",
     "negocio": "De onde veio o erro que gerou a glosa. Cadastro, sistema e faturamento são internos (evitáveis).",
     "tecnico": "CLASSIFICACAO normalizada: grafias como 'OPERAODRA' e 'SISITEMA' viram a canônica "
     "(regras.normalizar_classificacao)."},
]
INTERNAS = {"CADASTRO", "SISTEMA", "FATURAMENTO", "COMERCIAL", "CAPTAÇÃO", "NÚCLEO"}


def consultar(filtros):
    return montar(filtros.rodar("gp_por_classificacao"))


def montar(linhas):
    linhas = comum.ordenar(gp_comum.normalizar(linhas), "glosa")
    total = comum.com_participacao(linhas, "glosa")
    for i, l in enumerate(linhas):
        l["tom"] = TONS[i % len(TONS)]
        l["interna"] = l["classificacao"] in INTERNAS
    internas = sum(l["glosa"] for l in linhas if l["interna"])
    return {
        "vazio": not linhas,
        "grafico": comum.grafico("rosca", [l["classificacao"] for l in linhas],
                                 [{"nome": "Glosa", "tons": [l["tom"] for l in linhas],
                                   "valores": [l["glosa"] for l in linhas]}]),
        "linhas": linhas,
        "internas_pct": comum.pct(internas, total),
        "total": {"glosa": total, "linhas": sum(l["linhas"] for l in linhas)},
    }


def montar_amostra():
    return montar([
        {"classificacao": c, **gp_comum.amostra_somas(n, 0, g, 0, 0, 0, 0)}
        for c, n, g in [("OPERADORA", 1735, 4_900_000), ("CADASTRO", 1540, 2_600_000), ("SISTEMA", 804, 1_300_000),
                        ("FATURAMENTO", 622, 1_100_000), ("COMERCIAL", 152, 380_000), ("AUDITORIA", 150, 300_000)]
    ])
