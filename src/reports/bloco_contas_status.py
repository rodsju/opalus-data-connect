"""Contas do mês por situação no ciclo (aberta → liberada → exportada)."""

from . import comum
from .bloco_resumo import AMOSTRA_CONTAS

TITULO = "Contas por situação"
ICONE = "git-commit-horizontal"
PARTIAL = "reports/bloco_contas_status.html"
LARGURA = "inteira"
ITENS = [
    {
        "chave": "situacao",
        "titulo": "Situação da conta",
        "negocio": "Em que ponto do ciclo o faturamento do mês está, por unidade.",
        "tecnico": "CAPPAYMENT: SIMULATION=1 → Simulação; WRITEOFF=1 → Baixada; LIBERATED=0 → Aberta; "
        "EXPORTED=0 → Liberada; senão Exportada. Valor = faturamento do grupo (preço × (qtd − qtd coberta)). "
        "Contas sem item ficam de fora (JOIN com CAPPAYMENTITEM).",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("contas_por_status"))


def montar(linhas):
    situacoes = [s for s, _ in comum.SITUACOES_CONTA if any(l["situacao"] == s for l in linhas)]
    situacoes += sorted({l["situacao"] for l in linhas} - set(situacoes))

    # Valor da conta = faturamento do grupo (cobrado: fatura da operadora + particular)
    linhas = [{**l, "valor": l.get("faturamento_grupo")} for l in linhas]
    unidades = comum.ordenar(comum.somar_por(linhas, "unidade", ["valor"]), "valor")
    nomes = [u["unidade"] for u in unidades]
    valor = {(l["unidade"], l["situacao"]): comum.num(l["valor"]) for l in linhas}

    series = [
        {
            "nome": s,
            "tom": comum.TOM_SITUACAO_CONTA.get(s, "neutral"),
            "valores": [valor.get((u, s), 0) for u in nomes],
        }
        for s in situacoes
    ]

    resumo = comum.somar_por(linhas, "situacao", ["contas", "valor"])
    ordem = {s: i for i, s in enumerate(situacoes)}
    resumo.sort(key=lambda r: ordem.get(r["situacao"], 99))
    total = comum.com_participacao(resumo, "valor")
    for r in resumo:
        r["tom"] = comum.TOM_SITUACAO_CONTA.get(r["situacao"], "neutral")

    return {
        "vazio": not linhas,
        "grafico": comum.grafico("barras-h", nomes, series, empilhado=True),
        "altura": max(220, 42 * len(nomes) + 60),
        "resumo": resumo,
        "total": {"contas": sum(r["contas"] for r in resumo), "valor": total},
    }


def montar_amostra():
    return montar(AMOSTRA_CONTAS)
