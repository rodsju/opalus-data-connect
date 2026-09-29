"""Orçamentos do mês por situação de autorização."""

from .. import layout
from . import comum

TITULO = "Orçamentos por situação"
ICONE = "clipboard-list"
PARTIAL = "reports/bloco_orcamentos_status.html"
LARGURA = "inteira"
ITENS = [
    {
        "chave": "situacao",
        "titulo": "Situação do orçamento",
        "negocio": "Quantos orçamentos do mês já foram autorizados pela operadora, e quanto valem.",
        "tecnico": "CAPBUDGET: CANCELED=1 → Cancelado; AUTHORIZEXTSTATUS=1 → Autorizado (operadora); "
        "AUTHORIZINTSTATUS=1 → Autorizado (interno); LIBERATED=1 → Liberado; senão Pendente.",
    },
    {
        "chave": "valor",
        "titulo": "Valor previsto",
        "negocio": "Soma dos itens de cada orçamento. O valor autorizado não inclui os cancelados, que "
        "costumam ser versões substituídas por um orçamento novo.",
        "tecnico": "SUM(UNITPRICE × QUANTITY) em CAPBUDGETITEM (imposto, RESOURCETYPE 15, por UNITCOST). "
        "CAPBUDGET.BUDGETCHARGE não é usado: o ERP só o grava no cancelamento. Unidade pela dimensão "
        "CAPADMISSION → GLBHEALTHPROVDEP → GLBHEALTHPROVIDER.",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("orcamentos_por_status"))


def montar(linhas):
    resumo = comum.somar_por(linhas, "situacao", ["orcamentos", "valor_previsto"])
    ordem = {s: i for i, (s, _) in enumerate(comum.SITUACOES_ORCAMENTO)}
    resumo.sort(key=lambda r: ordem.get(r["situacao"], 99))
    total_qtd = sum(r["orcamentos"] for r in resumo)
    total_valor = sum(r["valor_previsto"] for r in resumo)
    for r in resumo:
        r["tom"] = comum.TOM_SITUACAO_ORCAMENTO.get(r["situacao"], "neutral")
        r["pct"] = comum.pct(r["orcamentos"], total_qtd)

    autorizados = [r for r in resumo if r["situacao"].startswith("Autorizado")]
    n_autorizados = sum(r["orcamentos"] for r in autorizados)
    cancelados = [r for r in resumo if r["situacao"] == "Cancelado"]
    n_cancelados = sum(r["orcamentos"] for r in cancelados)
    unidades = comum.ordenar(comum.somar_por(linhas, "unidade", ["orcamentos", "valor_previsto"]), "orcamentos")

    return {
        "vazio": not linhas,
        "cards": [
            {"rotulo": "Orçamentos", "valor": total_qtd, "formato": "int", "icone": "clipboard-list",
             "tom": "blue", "hint": f"{len(unidades)} unidades"},
            {"rotulo": "Autorizados", "valor": n_autorizados, "formato": "int", "icone": "badge-check",
             "tom": "teal", "barra": comum.pct(n_autorizados, total_qtd), "hint": "operadora + interno"},
            {"rotulo": "Valor autorizado", "valor": sum(r["valor_previsto"] for r in autorizados),
             "formato": "moeda_curta", "icone": "wallet", "tom": "violet", "hint": "soma dos itens dos autorizados"},
            {"rotulo": "Cancelados", "valor": n_cancelados, "formato": "int", "icone": "circle-x", "tom": "coral",
             "barra": comum.pct(n_cancelados, total_qtd),
             "hint": f"{layout.fmt_moeda_curta(sum(r['valor_previsto'] for r in cancelados))} em itens"},
        ],
        "grafico": comum.grafico(
            "rosca",
            [r["situacao"] for r in resumo],
            [{"nome": "Orçamentos", "tons": [r["tom"] for r in resumo], "valores": [r["orcamentos"] for r in resumo]}],
            formato="int",
        ),
        "resumo": resumo,
        "unidades": unidades[:12],
        "total": {"orcamentos": total_qtd, "valor_previsto": total_valor},
    }


AMOSTRA = [
    {"unidade": u, "empresa_homecare": "", "situacao": s, "orcamentos": q, "valor_previsto": v}
    for u, s, q, v in [
        ("Premier Brooklin HSP", "Autorizado (operadora)", 412, 3_820_000),
        ("Premier Brooklin HSP", "Pendente", 188, 410_000),
        ("Premier Brooklin HSP", "Liberado", 74, 260_000),
        ("Geriatrics SP HSP", "Autorizado (operadora)", 296, 2_140_000),
        ("Geriatrics SP HSP", "Autorizado (interno)", 51, 180_000),
        ("Geriatrics SP HSP", "Cancelado", 22, 0),
        ("Pleno Saúde - DF HSP", "Pendente", 97, 120_000),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
