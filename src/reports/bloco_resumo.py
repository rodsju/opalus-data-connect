"""Faixa de KPIs do faturamento do mês."""

from . import comum

TITULO = "Resumo do mês"
ICONE = "sparkles"
PARTIAL = "reports/bloco_resumo.html"
LARGURA = "faixa"
ITENS = [
    {
        "chave": "faturado",
        "titulo": "Faturamento do grupo e fatura da operadora",
        "negocio": "Faturamento do grupo = o que foi cobrado no mês (fora simulações): a fatura que vai para a "
        "operadora + o que o paciente paga (particular). O que estava incluso em pacote/diária não é cobrado.",
        "tecnico": "contas_por_status, situação ≠ 'Simulação'. Cobrado = SUM(UNITPRICE × (QTD − QTD COBERTA)); "
        "particular = conta cuja entidade é empresa do grupo (GLBENTERPRISE.CORPORATION=1). Validado contra a "
        "planilha de glosa do financeiro.",
    },
    {
        "chave": "aberto",
        "titulo": "Em aberto",
        "negocio": "Contas ainda não liberadas ou liberadas e não exportadas para a operadora.",
        "tecnico": "contas_por_status: situações 'Aberta (não liberada)' + 'Liberada (não exportada)'.",
    },
    {
        "chave": "glosa",
        "titulo": "Glosa e taxa de glosa",
        "negocio": "Quanto a operadora recusou. A glosa chega meses depois: mês recente parece limpo.",
        "tecnico": "glosa_por_unidade: SUM(AUDITBILLVALUE) / SUM(fatura da operadora).",
    },
    {
        "chave": "gap",
        "titulo": "Autorizado sem faturar",
        "negocio": "Orçamentos autorizados pela operadora que ainda não viraram item de conta.",
        "tecnico": "gap_resumo: CAPBUDGET autorizado, não cancelado, sem CAPPAYMENTITEM.IDBUDGET; valor "
        "= soma dos itens. Usa a dimensão GLBHEALTHPROVIDER, por isso só aparece sem filtro de unidade.",
    },
]


def consultar(filtros):
    contas = filtros.rodar("contas_por_status")
    glosa = filtros.rodar("glosa_por_unidade")
    # O gap vive na outra dimensão de unidade (provider): com filtro de homecare
    # ele zeraria em silêncio, então nem roda.
    gap = None
    if not filtros.unidade:
        try:
            gap = filtros.rodar("gap_resumo")
        except comum.ConsultaFalhou:
            gap = None
    return montar(contas, glosa, gap)


def montar(contas, glosa, gap):
    reais = [c for c in contas if c.get("situacao") != "Simulação"]
    soma = lambda linhas, campo: sum(comum.num(c.get(campo)) for c in linhas)  # noqa: E731
    faturado = soma(reais, "faturamento_grupo")
    operadora = soma(reais, "fatura_operadora")
    particular = soma(reais, "particular")
    n_contas = soma(reais, "contas")
    simulado = soma([c for c in contas if c.get("situacao") == "Simulação"], "faturamento_grupo")
    abertas = [c for c in reais if c.get("situacao") in comum.SITUACOES_ABERTAS]
    aberto = soma(abertas, "faturamento_grupo")
    fechado = soma([c for c in reais if c.get("situacao") == "Exportada (fechada)"], "faturamento_grupo")

    total_glosa = sum(comum.num(g.get("glosa")) for g in glosa)
    base_glosa = sum(comum.num(g.get("fatura_operadora")) for g in glosa)
    recuperada = sum(comum.num(g.get("glosa_recuperada")) for g in glosa)

    cards = [
        {
            "rotulo": "Faturamento do grupo",
            "valor": faturado,
            "formato": "moeda_curta",
            "hint": f"{int(n_contas)} contas · bruto {_curta(soma(reais, 'bruto'))}, "
                    f"pacote {_curta(soma(reais, 'pacote'))}" + (" · simulação fora" if simulado else ""),
            "icone": "banknote",
            "tom": "blue",
        },
        {
            "rotulo": "Fatura operadora",
            "valor": operadora,
            "formato": "moeda_curta",
            "barra": comum.pct(operadora, faturado),
            "hint": f"do grupo · particular {_curta(particular)}",
            "icone": "building-2",
            "tom": "cyan",
        },
        {
            "rotulo": "Exportado (fechado)",
            "valor": fechado,
            "formato": "moeda_curta",
            "barra": comum.pct(fechado, faturado),
            "hint": "do faturado já enviado",
            "icone": "send",
            "tom": "teal",
        },
        {
            "rotulo": "Em aberto",
            "valor": aberto,
            "formato": "moeda_curta",
            "barra": comum.pct(aberto, faturado),
            "hint": f"{int(sum(comum.num(c['contas']) for c in abertas))} contas a liberar/exportar",
            "icone": "hourglass",
            "tom": "amber",
        },
        {
            "rotulo": "Glosa",
            "valor": total_glosa,
            "formato": "moeda_curta",
            "hint": f"recuperada {_curta(recuperada)}",
            "icone": "shield-x",
            "tom": "coral",
        },
        {
            "rotulo": "Taxa de glosa",
            "valor": comum.pct(total_glosa, base_glosa),
            "formato": "pct",
            "hint": "glosa ÷ fatura operadora",
            "icone": "percent",
            "tom": "violet",
        },
    ]
    if gap is not None:
        valor_gap = sum(comum.num(g.get("valor_autorizado_pendente")) for g in gap)
        qtd_gap = int(sum(comum.num(g.get("autorizados_sem_faturamento")) for g in gap))
        # Sem valor nos itens, o card mostra a quantidade.
        cards.append(
            {
                "rotulo": "Autorizado sem faturar",
                "valor": valor_gap if valor_gap else qtd_gap,
                "formato": "moeda_curta" if valor_gap else "int",
                "hint": f"{qtd_gap} orçamentos" if valor_gap else "orçamentos · sem itens com valor",
                "icone": "file-clock",
                "tom": "magenta",
            }
        )
    return {"cards": cards, "vazio": not contas}


def _curta(valor):
    from .. import layout

    return layout.fmt_moeda_curta(valor)


def _amostra(unidade, situacao, contas, bruto, pacote, particular=0):
    cobrado = bruto - pacote
    return {"unidade": unidade, "situacao": situacao, "contas": contas, "bruto": bruto, "pacote": pacote,
            "faturamento_grupo": cobrado, "particular": particular, "fatura_operadora": cobrado - particular}


AMOSTRA_CONTAS = [
    _amostra("Premier Brooklin", "Exportada (fechada)", 212, 18_420_000, 7_300_000, 420_000),
    _amostra("Premier Brooklin", "Liberada (não exportada)", 38, 3_150_000, 1_200_000),
    _amostra("Premier Brooklin", "Aberta (não liberada)", 21, 1_730_000, 690_000, 80_000),
    _amostra("Geriatrics SP", "Exportada (fechada)", 164, 12_960_000, 5_100_000, 210_000),
    _amostra("Geriatrics SP", "Aberta (não liberada)", 17, 980_000, 400_000),
    _amostra("Pleno Saúde - DF", "Exportada (fechada)", 95, 7_450_000, 2_900_000),
    _amostra("Pleno Saúde - DF", "Simulação", 12, 610_000, 200_000),
]
AMOSTRA_GLOSA = [
    {"unidade": "Premier Brooklin", "fatura_operadora": 23_300_000, "glosa": 540_000, "glosa_recuperada": 180_000},
    {"unidade": "Geriatrics SP", "fatura_operadora": 13_940_000, "glosa": 310_000, "glosa_recuperada": 95_000},
    {"unidade": "Pleno Saúde - DF", "fatura_operadora": 7_450_000, "glosa": 128_000, "glosa_recuperada": 22_000},
]
AMOSTRA_GAP = [
    {"unidade": "Premier Brooklin HSP", "autorizados_sem_faturamento": 41, "valor_autorizado_pendente": 1_240_000},
    {"unidade": "Geriatrics SP HSP", "autorizados_sem_faturamento": 18, "valor_autorizado_pendente": 460_000},
]


def montar_amostra():
    return montar(AMOSTRA_CONTAS, AMOSTRA_GLOSA, AMOSTRA_GAP)
