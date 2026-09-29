"""Taxonomia dos motivos de glosa (classificação do texto livre)."""

from . import comum

TITULO = "Motivos de glosa"
ICONE = "tags"
PARTIAL = "reports/bloco_motivos_glosa.html"
LARGURA = "meia"
TONS = ["coral", "violet", "blue", "amber", "teal", "magenta", "cyan", "green", "navy", "neutral"]
ITENS = [
    {
        "chave": "motivo",
        "titulo": "Motivo",
        "negocio": "Por que a operadora glosou, agrupado em categorias de negócio.",
        "tecnico": "motivos_taxonomia: CASE ordenado sobre AUDITBILLCOMMENTS (o primeiro ramo que casa "
        "vence). AUDITBILLCODE (TISS) está vazio em 100% dos itens, por isso o texto.",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("motivos_taxonomia"))


def montar(linhas):
    linhas = comum.ordenar([dict(l) for l in linhas], "valor_glosa")
    total = comum.com_participacao(linhas, "valor_glosa")
    for i, l in enumerate(linhas):
        l["tom"] = TONS[i % len(TONS)]
    return {
        "vazio": not linhas,
        "grafico": comum.grafico(
            "rosca",
            [l["motivo"] for l in linhas],
            [{"nome": "Glosa", "tons": [l["tom"] for l in linhas], "valores": [l["valor_glosa"] for l in linhas]}],
        ),
        "linhas": linhas,
        "total": {"itens": sum(comum.num(l["itens"]) for l in linhas), "valor_glosa": total},
    }


AMOSTRA = [
    {"motivo": m, "itens": i, "valor_glosa": v}
    for m, i, v in [
        ("Divergência de senha/autorização", 312, 298_000),
        ("Divergência de código", 221, 187_000),
        ("Sem narrativa", 190, 142_000),
        ("Autorização tardia (senha pós-início)", 97, 121_000),
        ("Unidade de medida", 88, 64_000),
        ("Documentação/autorização em anexo", 61, 48_000),
        ("Outros", 57, 39_000),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
