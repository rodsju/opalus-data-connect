"""Orçamentos autorizados pela operadora que ainda não foram faturados."""

from . import comum

TITULO = "Autorizado sem faturamento"
ICONE = "file-clock"
PARTIAL = "reports/bloco_gap_orcamento.html"
LARGURA = "inteira"
ITENS = [
    {
        "chave": "gap",
        "titulo": "Gap orçamento → faturamento",
        "negocio": "Receita já autorizada que ainda não virou conta: dinheiro na mesa.",
        "tecnico": "gap_resumo: CAPBUDGET com AUTHORIZEXTSTATUS=1, CANCELED=0 e NOT EXISTS em "
        "CAPPAYMENTITEM.IDBUDGET. Valor = soma dos itens (CAPBUDGETITEM, imposto por UNITCOST).",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("gap_resumo"))


def montar(linhas):
    linhas = comum.ordenar([dict(l) for l in linhas], "valor_autorizado_pendente")
    total = comum.com_participacao(linhas, "valor_autorizado_pendente")
    topo = linhas[:12]
    # Orçamento sem item soma zero: aí o gráfico mostra a quantidade em vez de
    # barras zeradas.
    sem_valor = not total
    if sem_valor:
        topo = comum.ordenar(linhas, "autorizados_sem_faturamento")[:12]
    return {
        "vazio": not linhas,
        "sem_valor": sem_valor,
        "grafico": comum.grafico(
            "barras-h",
            [l["unidade"] for l in topo],
            [{"nome": "Orçamentos" if sem_valor else "Autorizado pendente", "tom": "magenta",
              "valores": [l["autorizados_sem_faturamento" if sem_valor else "valor_autorizado_pendente"]
                          for l in topo]}],
            formato="int" if sem_valor else "moeda",
            gradiente=True,
        ),
        "altura": max(200, 34 * len(topo) + 50),
        "linhas": linhas,
        "total": {
            "autorizados_sem_faturamento": sum(comum.num(l["autorizados_sem_faturamento"]) for l in linhas),
            "valor_autorizado_pendente": total,
        },
    }


AMOSTRA = [
    {"unidade": "Premier Brooklin HSP", "autorizados_sem_faturamento": 41, "valor_autorizado_pendente": 1_240_000},
    {"unidade": "Geriatrics SP HSP", "autorizados_sem_faturamento": 18, "valor_autorizado_pendente": 460_000},
    {"unidade": "Premier Moema HSP", "autorizados_sem_faturamento": 12, "valor_autorizado_pendente": 318_000},
    {"unidade": "Pleno Saúde - DF HSP", "autorizados_sem_faturamento": 7, "valor_autorizado_pendente": 96_000},
]


def montar_amostra():
    return montar(AMOSTRA)
