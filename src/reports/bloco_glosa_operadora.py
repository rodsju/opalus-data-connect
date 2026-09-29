"""Glosa por operadora, separando sustentada, recuperada e pendente."""

from . import comum

TITULO = "Glosa por operadora"
ICONE = "building-2"
PARTIAL = "reports/bloco_glosa_operadora.html"
LARGURA = "meia"
ITENS = [
    {
        "chave": "glosa",
        "titulo": "Composição da glosa",
        "negocio": "Quais operadoras mais glosam e quanto disso já foi decidido.",
        "tecnico": "glosa_por_operadora: itens com AUDITBILLVALUE > 0. Pendente = glosa − sustentada − "
        "recuperada (piso zero).",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("glosa_por_operadora"))


def montar(linhas):
    linhas = comum.ordenar([dict(l) for l in linhas], "glosa")
    for l in linhas:
        l["pendente"] = max(
            comum.num(l["glosa"]) - comum.num(l["glosa_sustentada"]) - comum.num(l["glosa_recuperada"]), 0
        )
    total = comum.com_participacao(linhas, "glosa")
    topo = linhas[:8]
    rotulos = [l["operadora"] for l in topo]
    return {
        "vazio": not linhas,
        "grafico": comum.grafico(
            "barras-h",
            rotulos,
            [
                {"nome": "Recuperada", "tom": "teal", "valores": [l["glosa_recuperada"] for l in topo]},
                {"nome": "Sustentada", "tom": "coral", "valores": [l["glosa_sustentada"] for l in topo]},
                {"nome": "Pendente", "tom": "amber", "valores": [l["pendente"] for l in topo]},
            ],
            empilhado=True,
        ),
        "altura": max(200, 36 * len(topo) + 60),
        "linhas": comum.top_com_outros(linhas, "operadora", ["itens_glosados", "glosa", "pct"], 8),
        "total": {"itens_glosados": sum(comum.num(l["itens_glosados"]) for l in linhas), "glosa": total},
    }


AMOSTRA = [
    {"operadora": op, "itens_glosados": i, "glosa": g, "glosa_sustentada": s, "glosa_recuperada": r}
    for op, i, g, s, r in [
        ("Bradesco Saúde", 402, 388_000, 150_000, 120_000),
        ("SulAmérica", 251, 241_000, 98_000, 71_000),
        ("Amil", 188, 172_000, 81_000, 30_000),
        ("Unimed Seguros", 131, 118_000, 40_000, 52_000),
        ("Cassi", 64, 61_000, 21_000, 8_000),
        ("Porto Seguro Saúde", 42, 38_500, 11_000, 9_500),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
