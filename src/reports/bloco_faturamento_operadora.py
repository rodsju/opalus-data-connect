"""Concentração do faturamento por operadora (pareto)."""

from . import comum

TITULO = "Faturamento por entidade pagadora"
ICONE = "building-2"
PARTIAL = "reports/bloco_faturamento_operadora.html"
LARGURA = "inteira"
TOP = 10
ITENS = [
    {
        "chave": "operadora",
        "titulo": "Operadora",
        "negocio": "Quem paga o faturamento do mês e quanto as maiores concentram. Operadora recebe a fatura "
        "(NF); particular é cobrado do paciente pela própria empresa do grupo.",
        "tecnico": "faturamento_por_operadora: CAPPAYMENT.IDENTERPRISE → GLBENTERPRISE, sem simulação, somado "
        "entre unidades. Valor = faturamento do grupo (preço × (qtd − qtd coberta)); pagador 'particular' quando a "
        "entidade é empresa do grupo (CORPORATION=1).",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("faturamento_por_operadora"))


def montar(linhas):
    linhas = [{**l, "valor_faturado": l.get("faturamento_grupo")} for l in linhas]
    operadoras = comum.ordenar(comum.somar_por(linhas, "operadora", ["contas", "valor_faturado"]), "valor_faturado")
    pagador = {l["operadora"]: l.get("pagador") for l in linhas}
    for o in operadoras:
        o["particular"] = pagador.get(o["operadora"]) == "particular"
    total = comum.com_participacao(operadoras, "valor_faturado")
    topo = operadoras[:TOP]
    tabela = comum.top_com_outros(operadoras, "operadora", ["contas", "valor_faturado", "pct"], 15)
    return {
        "vazio": not linhas,
        "grafico": comum.grafico(
            "barras-h",
            [o["operadora"] for o in topo],
            [{"nome": "Faturamento", "tom": "blue", "valores": [o["valor_faturado"] for o in topo]}],
            gradiente=True,
        ),
        "altura": max(220, 34 * len(topo) + 50),
        "linhas": tabela,
        "total": {"contas": sum(o["contas"] for o in operadoras), "valor_faturado": total},
        "n_operadoras": len(operadoras),
        "top3_pct": operadoras[2]["pct_acum"] if len(operadoras) >= 3 else None,
    }


AMOSTRA = [
    {"unidade": "Premier Brooklin", "operadora": op, "contas": c, "faturamento_grupo": v,
     "pagador": "particular" if op.startswith("Premier") else "operadora"}
    for op, c, v in [
        ("Bradesco Saúde", 118, 9_840_000),
        ("SulAmérica", 84, 6_120_000),
        ("Amil", 61, 4_380_000),
        ("Unimed Seguros", 47, 3_260_000),
        ("Porto Seguro Saúde", 33, 2_410_000),
        ("Cassi", 26, 1_880_000),
        ("Mediservice", 19, 1_120_000),
        ("Premier Flamengo", 22, 940_000),
        ("Care Plus", 11, 610_000),
        ("Omint", 8, 480_000),
        ("Allianz Saúde", 6, 290_000),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
