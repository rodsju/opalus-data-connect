"""Pré-auditoria: a glosa interna, cortada antes de a conta ir para a operadora."""

import datetime

from . import comum, fonte

TITULO = "Pré-auditoria (glosa interna)"
ICONE = "scan-search"
PARTIAL = "reports/bloco_pre_auditoria.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "pre", "titulo": "Cortado na pré-auditoria",
     "negocio": "O que a auditoria interna tirou da conta ANTES do envio: excesso, item fora do plano, falta de "
     "assinatura. Já está fora do faturado; na cascata é um passo próprio, separado do pacote.",
     "tecnico": "CAPPAYMENTITEM.PREAUDITBILL*: o corte é gravado como cobertura (PREAUDITBILLQUANT = "
     "COVERAGEQUANTITY em 97% dos itens). Valor = UNITPRICE × LEAST(qtd pré-auditada, qtd coberta)."},
    {"chave": "segurou", "titulo": "Segurou",
     "negocio": "Dos itens pré-auditados, quantos a operadora NÃO glosou depois. Alto = a pré-auditoria está "
     "tirando o que seria glosado.",
     "tecnico": "Itens pré-auditados sem AUDITBILLVALUE. A glosa IW parou em jul/2025: depois disso, "
     "'sem glosa' também inclui o que não foi registrado."},
    {"chave": "motivo", "titulo": "Motivo",
     "negocio": "Códigos 1 a 4 são internos (Premissas › Motivos internos da pré-auditoria); os demais são TISS.",
     "tecnico": "PREAUDITBILLREASON; descrição do parâmetro interno ou da Tabela 38 sincronizada."},
]

MESES = 12


def descricoes():
    """{código: (descrição, origem)} dos motivos internos e TISS. Vazio se o Postgres falhar."""
    try:
        return {l["codigo"]: (l["descricao"], l["origem"]) for l in fonte.rodar("pa_motivos", {})}
    except comum.ConsultaFalhou:
        return {}


def _doze_meses(filtros):
    params = filtros.params()
    inicio = filtros.inicio
    for _ in range(MESES - 1):
        inicio = (inicio - datetime.timedelta(days=1)).replace(day=1)
    params["DT_INI"] = inicio
    return fonte.rodar("pre_auditoria_por_mes", params)


def consultar(filtros):
    cascata = filtros.rodar("cascata_por_pagador")
    return montar(filtros.rodar("pre_auditoria_por_motivo"), filtros.rodar("pre_auditoria_por_operadora"),
                  _doze_meses(filtros), sum(comum.num(l.get("bruto")) for l in cascata), descricoes(), filtros)


def montar(motivos, operadoras, meses, bruto, textos, filtros=None):
    meses = sorted(meses, key=lambda m: m["grupo"])
    valor = sum(comum.num(l["pre_auditoria"]) for l in motivos)
    itens = sum(int(comum.num(l["itens"])) for l in motivos)
    glosados = sum(int(comum.num(l["itens_glosados_depois"])) for l in motivos)
    linhas_motivo = []
    for l in motivos:
        descricao, origem = textos.get(l["grupo"], (None, None))
        linhas_motivo.append({**l, "descricao": descricao, "origem": origem,
                              "pct": comum.pct(l["pre_auditoria"], valor)})
    top = linhas_motivo[:10]
    top_op = operadoras[:10]
    return {
        "vazio": not motivos and not meses,
        "kpis": [
            {"rotulo": "Cortado antes do envio", "valor": valor, "formato": "moeda_curta", "icone": "scan-search",
             "tom": "violet", "hint": f"{(comum.pct(valor, bruto) or 0):.2f}% do bruto lançado".replace(".", ",")},
            {"rotulo": "Itens pré-auditados", "valor": itens, "formato": "int", "icone": "list-checks",
             "tom": "blue", "hint": f"{sum(int(comum.num(l['contas'])) for l in operadoras)} contas"},
            {"rotulo": "Segurou", "valor": comum.pct(itens - glosados, itens), "formato": "pct",
             "icone": "shield-check", "tom": "teal",
             "hint": f"{glosados} itens glosados depois · glosa IW só registrada até jul/2025"},
        ],
        "motivos": linhas_motivo,
        "grafico_motivos": comum.grafico("barras-h", [
            f"{l['grupo']} · {(l['descricao'] or '')[:30]}" if l["descricao"] else l["grupo"] for l in top],
            [{"nome": "Pré-auditoria", "tom": "violet", "valores": [l["pre_auditoria"] for l in top]}],
            gradiente=True) if top else None,
        "grafico_operadoras": comum.grafico("barras-h", [l["grupo"] for l in top_op],
            [{"nome": "Pré-auditoria", "tom": "blue", "valores": [l["pre_auditoria"] for l in top_op]}],
            gradiente=True) if top_op else None,
        "grafico_meses": comum.grafico("barras", [l["grupo"] for l in meses], [
            {"nome": "Pré-auditoria", "tom": "violet", "valores": [l["pre_auditoria"] for l in meses]},
        ], gradiente=True) if meses else None,
        "link": "/consultas/pre-auditoria" + (f"?mes={filtros.mes}&unidade={filtros.unidade}&tipo={filtros.tipo}"
                                             if filtros else ""),
    }


def montar_amostra():
    motivos = [
        {"grupo": "2", "itens": 12, "contas": 4, "pre_auditoria": 18_400, "itens_glosados_depois": 0},
        {"grupo": "2109", "itens": 9, "contas": 3, "pre_auditoria": 6_200, "itens_glosados_depois": 1},
        {"grupo": "3", "itens": 7, "contas": 2, "pre_auditoria": 3_100, "itens_glosados_depois": 0},
    ]
    operadoras = [{"grupo": "Amil", "itens": 15, "contas": 5, "pre_auditoria": 17_000, "itens_glosados_depois": 1},
                  {"grupo": "Bradesco", "itens": 13, "contas": 4, "pre_auditoria": 10_700, "itens_glosados_depois": 0}]
    meses = [{"grupo": f"2026-{m:02d}", "itens": 20 + m, "pre_auditoria": 9_000 + m * 1_500} for m in range(1, 9)]
    textos = {"2": ("Interno: envio em excesso", "interno"), "2109": ("Cobrança de taxa inválida", "tiss"),
              "3": ("Interno: registro de ponto", "interno")}
    return montar(motivos, operadoras, meses, 31_000_000, textos)
