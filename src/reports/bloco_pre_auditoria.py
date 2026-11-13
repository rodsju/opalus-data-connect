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
    {"chave": "glosadas", "titulo": "Pré-auditadas e glosadas",
     "negocio": "Contas do paciente que passaram pela pré-auditoria e mesmo assim a operadora glosou. Alto = a "
     "pré-auditoria não está pegando o que a operadora glosa. A glosa chega meses depois: mês recente parece limpo.",
     "tecnico": "Conta × admissão com item pré-auditado no mês, casada com a glosa da carga ativa da planilha/XML "
     "(cp_glosas: por admissão, ou pelo paciente quando a linha foi casada pelo total). A planilha não desce a "
     "item: a glosa é do paciente na conta, não necessariamente do item cortado."},
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


def glosadas(itens, glosas):
    """(pré-auditadas, glosadas, valor): contas do paciente (conta × admissão) com item pré-auditado e,
    entre elas, as que têm glosa na planilha. `glosas` None = sem planilha: glosadas e valor ficam None."""
    pares = {(i["id_conta"], i.get("id_admissao"), i.get("id_paciente")) for i in itens}
    if glosas is None:
        return len(pares), None, None
    por_chave = {}
    for g in glosas:
        chave = (g["id_conta"], "A", g["id_admissao"]) if g.get("id_admissao") else (g["id_conta"], "P", g["id_paciente"])
        por_chave[chave] = comum.num(g.get("glosa"))
    n, valor, usadas = 0, 0.0, set()
    for conta, admissao, paciente in pares:
        chave = (conta, "A", admissao)
        if chave not in por_chave:
            chave = (conta, "P", paciente)
        if por_chave.get(chave, 0) > 0:
            n += 1
            if chave not in usadas:  # glosa casada pelo paciente vale uma vez só
                usadas.add(chave)
                valor += por_chave[chave]
    return len(pares), n, valor


def _glosadas(filtros):
    itens = filtros.rodar("pre_auditoria_itens")
    contas = sorted({i["id_conta"] for i in itens})
    if not contas:
        return glosadas([], [])
    try:
        return glosadas(itens, fonte.rodar("cp_glosas", {"CONTAS": contas}))
    except comum.ConsultaFalhou:
        return glosadas(itens, None)


def consultar(filtros):
    cascata = filtros.rodar("cascata_por_pagador")
    return montar(filtros.rodar("pre_auditoria_por_motivo"), filtros.rodar("pre_auditoria_por_operadora"),
                  _doze_meses(filtros), sum(comum.num(l.get("bruto")) for l in cascata), descricoes(), filtros,
                  _glosadas(filtros))


def _card_glosadas(pre_auditadas, n, valor):
    card = {"rotulo": "Pré-auditadas e glosadas", "icone": "shield-alert", "tom": "coral", "formato": "int"}
    if n is None:
        return {**card, "valor": None, "hint": "sem planilha de glosa carregada"}
    return {**card, "valor": n, "barra": comum.pct(n, pre_auditadas),
            "hint": f"de {pre_auditadas} contas do paciente pré-auditadas"
                    + (f" · glosa {_curta(valor)} (planilha)" if n else " · glosa chega meses depois")}


def _curta(valor):
    from .. import layout

    return layout.fmt_moeda_curta(valor)


def montar(motivos, operadoras, meses, bruto, textos, filtros=None, contas_glosadas=(0, 0, 0.0)):
    meses = sorted(meses, key=lambda m: m["grupo"])
    valor = sum(comum.num(l["pre_auditoria"]) for l in motivos)
    itens = sum(int(comum.num(l["itens"])) for l in motivos)
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
            _card_glosadas(*contas_glosadas),
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
    return montar(motivos, operadoras, meses, 31_000_000, textos, contas_glosadas=(9, 2, 14_300))
