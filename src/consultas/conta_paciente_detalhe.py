"""Detalhe de uma linha da Conta do paciente: orçamento, fatura item a item, pré-auditoria e glosa.

A linha é conta × admissão × orçamento (0 = sem admissão / sem orçamento). O
orçamento aparece inteiro (todos os itens, mesmo os faturados em outra conta);
a fatura só com os itens desta conta, deste paciente e deste orçamento. A glosa
da planilha é do paciente na conta, não do orçamento.
"""

import concurrent.futures

from .. import layout
from ..reports import bloco_pre_auditoria, comum, fonte, orcamento_risco
from . import conta_paciente, lista


def _pg(nome, params, padrao):
    try:
        return fonte.rodar(nome, params)
    except comum.ConsultaFalhou:
        return padrao


def _por_recurso(itens):
    """Itens da fatura -> formato de orcamento_risco.comparar_itens, com a pré-auditoria por recurso."""
    por = {}
    for i in itens:
        r = por.setdefault(i["recurso_id"], {"recurso_id": i["recurso_id"], "recurso": i["recurso"],
                                             "categoria": i["categoria"], "qtd": 0.0, "qtd_coberta": 0.0,
                                             "preco": i["preco"], "bruto": 0.0, "pacote": 0.0, "cobrado": 0.0,
                                             "glosa_iw": 0.0, "qtd_pre": 0.0, "pre_auditoria": 0.0})
        for c in ("qtd", "qtd_coberta", "bruto", "pacote", "cobrado", "glosa_iw", "qtd_pre", "pre_auditoria"):
            r[c] += comum.num(i[c])
    return list(por.values())


def montar(id_conta, id_admissao, id_orcamento):
    """Contexto do detalhe, ou None se a linha não existe."""
    chave = {"ID": id_conta, "ADMISSAO": id_admissao, "ORCAMENTO": id_orcamento}
    consultas = {"linha": ("conta_paciente_linha", chave), "itens": ("conta_paciente_itens", chave),
                 "irmaos": ("conta_paciente_irmaos", {"ID": id_conta, "ADMISSAO": id_admissao})}
    if id_orcamento:
        consultas["orcamento"] = ("orcamento_cabecalho", {"ID": id_orcamento})
        consultas["orcamento_itens"] = ("orcamento_itens", {"ID": id_orcamento})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futuros = {k: pool.submit(fonte.rodar, n, p) for k, (n, p) in consultas.items()}
        dados = {k: f.result() for k, f in futuros.items()}
    if not dados["linha"]:
        return None
    bruta = dados["linha"][0]
    glosas_linhas = _pg("cp_glosa_linhas", {"CONTA": id_conta, "ADMISSAO": id_admissao or None,
                                            "PACIENTE": bruta.get("id_paciente")}, [])
    chave_pg = {"CONTA": id_conta, "ADMISSAO": id_admissao or None}
    tiss_guias = _pg("cp_tiss_guias", chave_pg, []) if id_admissao else []
    tiss_itens = _pg("cp_tiss_itens", chave_pg, []) if id_admissao else []
    grupos = _pg("cp_glosas", {"CONTAS": [id_conta]}, [])
    glosas = {((g["id_conta"], "A", g["id_admissao"]) if g["id_admissao"] else (g["id_conta"], "P", g["id_paciente"])): g
              for g in grupos}
    orcamento = dados["orcamento"][0] if dados.get("orcamento") else None
    if orcamento:
        orcamento = {**orcamento, **{k: conta_paciente._data(orcamento.get(k)) for k in ("inicio", "fim", "validade_senha")}}
    valores = {id_orcamento: {"orcado": orcamento["orcado"], "situacao_orcamento": orcamento["situacao"],
                              "orcamento_inicio": orcamento["inicio"], "orcamento_fim": orcamento["fim"]}} \
        if orcamento else {}
    # Irmãos primeiro, para a glosa cair na primeira linha do paciente como na lista
    todas = conta_paciente.juntar(dados["irmaos"], valores, glosas)
    linha = next(l for l in todas if (l.get("id_orcamento") or 0) == id_orcamento)
    linha["data_entrega"] = conta_paciente._data(linha.get("data_entrega"))
    textos = bloco_pre_auditoria.descricoes()
    itens = [{**i, "motivo_pre_descricao": textos.get(i["motivo_pre"], (None,))[0]} for i in dados["itens"]]
    recurso_erp = {i["id_item"]: i["recurso"] for i in itens}
    for t in tiss_itens:
        t["motivos_texto"] = [f"{m['codigo']} · {(textos.get(m['codigo'], ('',))[0] or '').capitalize()}".strip(" ·")
                              for m in (t.get("motivos") or [])]
        t["recurso_erp"] = recurso_erp.get(t.get("id_item_erp"))
    for g in glosas_linhas:
        g["origem_rotulo"] = f"({g.get('origem_glosa') or 'planilha'})"
    alterados = [i for i in itens if i["alterado_pre"]]
    comparacao = orcamento_risco.comparar_itens(dados.get("orcamento_itens", []), _por_recurso(itens)) \
        if id_orcamento else []
    pre_por_recurso = {r["recurso_id"]: r for r in _por_recurso(itens)}
    for c in comparacao:
        r = pre_por_recurso.get(c["recurso_id"])
        c["qtd_pre"], c["pre_auditoria"] = (r["qtd_pre"], r["pre_auditoria"]) if r else (0, 0)
    t = lambda c: comum.num(linha.get(c))  # noqa: E731
    return {
        "linha": linha,
        "orcamento": orcamento,
        "orcamento_itens": dados.get("orcamento_itens", []),
        "itens": itens,
        "alterados": alterados,
        "comparacao": comparacao,
        "glosas": glosas_linhas,
        "tiss_guias": tiss_guias,
        "tiss_itens": tiss_itens,
        "glosa_do_paciente": len([l for l in todas if l.get("id_orcamento")]) > 1,
        "irmaos": [l for l in todas if l["detalhe"] != linha["detalhe"]],
        "cascata": comum.cascata([
            ("Bruto lançado", t("bruto"), "total", "itens desta conta, paciente e orçamento"),
            ("Incluso em pacote", t("pacote"), "neg", "coberto por diária/pacote"),
            ("Pré-auditoria", t("pre_auditoria"), "neg", "cortado antes do envio"),
            ("Faturamento", t("faturamento_grupo"), "total", "o que foi cobrado"),
            ("Particular", t("particular"), "neg", "cobrado do paciente"),
            ("Fatura operadora", t("fatura_operadora"), "total", "vai na nota para a operadora"),
        ]),
    }


def gerar(usuario, id_conta, id_admissao, id_orcamento):
    erro = None
    try:
        ctx = montar(id_conta, id_admissao, id_orcamento)
    except comum.ConsultaFalhou as falha:
        ctx, erro = None, {"motivo": falha.motivo, "detalhe": falha.dica}
    if ctx is None and not erro:
        return None, 404
    titulo = f"Conta {id_conta}" + (f" · orçamento {id_orcamento}" if id_orcamento else "")
    html = layout.render(
        "consultas/conta_paciente_detalhe.html", titulo, usuario, "/consultas/conta-paciente",
        ctx=ctx, erro=erro, id_conta=id_conta, id_orcamento=id_orcamento, titulo_pagina=titulo,
        consultas=lista.CONSULTAS_MENU)
    return html, 200
