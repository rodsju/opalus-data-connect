"""Contas do mês ainda em aberto, por operadora."""

from . import comum

TITULO = "Em aberto por operadora"
ICONE = "hourglass"
PARTIAL = "reports/bloco_contas_abertas.html"
LARGURA = "meia"
ITENS = [
    {
        "chave": "aberto",
        "titulo": "Conta em aberto",
        "negocio": "Faturamento parado antes de chegar à operadora: não liberado ou não exportado.",
        "tecnico": "contas_em_aberto: SIMULATION=0, WRITEOFF=0 e (LIBERATED=0 ou EXPORTED=0). Valor = faturamento "
        "do grupo (preço × (qtd − qtd coberta)).",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("contas_em_aberto"))


def montar(linhas):
    linhas = comum.ordenar([{**l, "valor_aberto": l.get("faturamento_grupo")} for l in linhas], "valor_aberto")
    total = comum.com_participacao(linhas, "valor_aberto")
    topo = linhas[:8]
    return {
        "vazio": not linhas,
        "grafico": comum.grafico(
            "barras-h",
            [l["operadora"] for l in topo],
            [{"nome": "Em aberto", "tom": "amber", "valores": [l["valor_aberto"] for l in topo]}],
        ),
        "altura": max(200, 34 * len(topo) + 50),
        "linhas": comum.top_com_outros(linhas, "operadora", ["contas_abertas", "valor_aberto", "pct"], 8),
        "total": {"contas_abertas": sum(comum.num(l["contas_abertas"]) for l in linhas), "valor_aberto": total},
    }


AMOSTRA = [
    {"operadora": o, "contas_abertas": n, "faturamento_grupo": v}
    for o, n, v in [("Bradesco Saúde", 19, 1_620_000), ("SulAmérica", 14, 1_140_000), ("Amil", 11, 860_000),
                    ("Unimed Seguros", 9, 590_000), ("Cassi", 5, 310_000), ("Premier Flamengo", 4, 140_000)]
]


def montar_amostra():
    return montar(AMOSTRA)
