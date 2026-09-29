"""Glosa por unidade: faturado × glosado e a taxa de glosa."""

from . import comum

TITULO = "Glosa por unidade"
ICONE = "shield-x"
PARTIAL = "reports/bloco_glosa_unidade.html"
LARGURA = "inteira"
ITENS = [
    {
        "chave": "glosa",
        "titulo": "Glosa",
        "negocio": "Valor recusado pela operadora na auditoria da conta. Sustentada = mantida; "
        "recuperada = revertida em recurso.",
        "tecnico": "glosa_por_unidade: SUM(AUDITBILLVALUE / AUDITBILLSUSTAINED / AUDITBILLRECOVERED), "
        "sem simulação, pela competência da conta (CAPPAYMENT.STARTDATE).",
    },
    {
        "chave": "taxa",
        "titulo": "Taxa de glosa",
        "negocio": "Glosa ÷ faturado. A glosa chega meses depois da competência: meses recentes "
        "parecem artificialmente limpos.",
        "tecnico": "SUM(AUDITBILLVALUE) / NULLIF(SUM(fatura da operadora), 0) × 100; fatura = preço × (qtd − "
        "qtd coberta), sem as contas particulares.",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("glosa_por_unidade"))


def montar(linhas):
    campos = ["itens", "itens_glosados", "faturado", "glosa", "glosa_sustentada", "glosa_recuperada"]
    linhas = comum.ordenar([{**{k: l.get(k) for k in ["unidade", *campos]}, "faturado": l.get("fatura_operadora")}
                            for l in linhas], "glosa")
    for l in linhas:
        l["taxa"] = comum.pct(l["glosa"], l["faturado"])
    total = {c: sum(comum.num(l[c]) for l in linhas) for c in campos}
    total["taxa"] = comum.pct(total["glosa"], total["faturado"])
    topo = linhas[:12]
    return {
        "vazio": not linhas,
        "cards": [
            {"rotulo": "Glosa total", "valor": total["glosa"], "formato": "moeda_curta", "icone": "shield-x",
             "tom": "coral", "hint": f"{int(total['itens_glosados'])} itens glosados"},
            {"rotulo": "Taxa de glosa", "valor": total["taxa"], "formato": "pct", "icone": "percent",
             "tom": "violet", "hint": "sobre o faturado"},
            {"rotulo": "Sustentada", "valor": total["glosa_sustentada"], "formato": "moeda_curta",
             "icone": "lock", "tom": "amber", "barra": comum.pct(total["glosa_sustentada"], total["glosa"])},
            {"rotulo": "Recuperada", "valor": total["glosa_recuperada"], "formato": "moeda_curta",
             "icone": "rotate-ccw", "tom": "teal", "barra": comum.pct(total["glosa_recuperada"], total["glosa"])},
        ],
        "grafico": comum.grafico(
            "barras-linha",
            [l["unidade"] for l in topo],
            [
                {"nome": "Glosa", "tom": "coral", "valores": [l["glosa"] for l in topo]},
                {"nome": "Taxa de glosa", "tom": "violet", "tipo": "linha", "eixo": "pct",
                 "valores": [l["taxa"] or 0 for l in topo]},
            ],
        ),
        "linhas": linhas,
        "total": total,
    }


AMOSTRA = [
    {"unidade": u, "itens": i, "itens_glosados": g, "fatura_operadora": f, "glosa": gl,
     "glosa_sustentada": s, "glosa_recuperada": r}
    for u, i, g, f, gl, s, r in [
        ("Premier Brooklin", 48_210, 612, 23_300_000, 540_000, 210_000, 180_000),
        ("Geriatrics SP", 31_880, 344, 13_940_000, 310_000, 140_000, 95_000),
        ("Pleno Saúde - DF", 14_320, 121, 7_450_000, 128_000, 61_000, 22_000),
        ("Premier Moema", 9_870, 88, 4_210_000, 142_000, 30_000, 41_000),
        ("Pleno Saúde - ES", 6_110, 23, 2_060_000, 18_500, 9_000, 3_100),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
