"""Guias exportadas à operadora que ainda não têm retorno (XML TISS de volta ou planilha de glosa), por operadora."""

from . import comum, fonte

TITULO = "Exportadas sem retorno da operadora"
ICONE = "inbox"
PARTIAL = "reports/bloco_retorno_operadora.html"
LARGURA = "inteira"
LOTE = 900
ITENS = [
    {
        "chave": "sem_retorno",
        "titulo": "Sem retorno",
        "negocio": "Guias já exportadas para a operadora que ainda não foram conciliadas: nem o demonstrativo "
        "(XML TISS de volta) nem a planilha de glosa trazem a guia. A planilha só tem guia glosada: guia paga "
        "sem glosa só sai daqui com o XML. O retorno leva semanas: mês recente sem retorno é esperado.",
        "tecnico": "exportadas_por_guia: conta Exportada (fechada), fora particular, uma linha por conta × admissão "
        "(= numeroGuiaPrestador); valor = faturável. Retorno = guia do XML ativa (tiss_guia_ativa) ou linha da "
        "carga ativa da planilha (cruzamento CONCILIADO/DIVERGENTE) casada com a mesma conta × admissão (ou pelo "
        "paciente, quando a planilha casou pelo total). Com as duas, vale o XML.",
    },
    {
        "chave": "divergente",
        "titulo": "Retorno divergente",
        "negocio": "A operadora devolveu a guia, mas o valor informado no XML não bate com o faturável do ERP.",
        "tecnico": "tiss_guia_ativa.situacao = 'DIVERGENTE' (tolerância R$ 1, tiss_cruzamento.py).",
    },
]


def _retornos(nome, contas):
    lista, saida = sorted(contas), []
    for inicio in range(0, len(lista), LOTE):
        saida += fonte.rodar(nome, {"CONTAS": lista[inicio:inicio + LOTE]})
    return saida


def consultar(filtros):
    guias = filtros.rodar("exportadas_por_guia")
    contas = {g["id_conta"] for g in guias}
    try:
        xml = _retornos("tiss_retornos", contas) if guias else []
        planilha = _retornos("planilha_retornos", contas) if guias else []
        resumo = (fonte.rodar("tiss_arquivos_resumo", {}) or [{}])[0]
    except comum.ConsultaFalhou:
        xml, planilha, resumo = None, None, None
    return montar(guias, xml, planilha, resumo)


def retorno(guia, xml, planilha):
    """(situação, origem) da guia: XML primeiro (é o retorno da própria operadora), depois a planilha,
    por admissão ou, na linha casada pelo total, pelo paciente. (None, None) = sem retorno."""
    chave = (guia["id_conta"], guia["id_admissao"])
    if chave in xml:
        return xml[chave], "xml"
    for chave in (("A",) + chave, ("P", guia["id_conta"], guia.get("id_paciente"))):
        if chave in planilha:
            return planilha[chave], "planilha"
    return None, None


def montar(guias, xml, planilha, resumo):
    """xml/planilha None = Conciliação (Postgres) indisponível: o bloco diz isso em vez de tudo 'sem retorno'."""
    por_xml = {(r["id_conta"], r["id_admissao"]): r["situacao"] for r in (xml or [])}
    por_planilha = {(("A", r["id_conta"], r["id_admissao"]) if r.get("id_admissao")
                     else ("P", r["id_conta"], r.get("id_paciente"))): r["situacao"] for r in (planilha or [])}
    origens = {"xml": 0, "planilha": 0}
    por_op = {}
    for g in guias:
        o = por_op.setdefault(g["operadora"], {"operadora": g["operadora"], "guias": 0, "exportado": 0.0,
                                               "sem_retorno": 0.0, "guias_sem_retorno": 0, "divergente": 0.0,
                                               "conciliado": 0.0})
        valor = comum.num(g["faturavel"])
        o["guias"] += 1
        o["exportado"] += valor
        sit, origem = retorno(g, por_xml, por_planilha)
        if origem:
            origens[origem] += 1
        if sit is None:
            o["sem_retorno"] += valor
            o["guias_sem_retorno"] += 1
        elif sit == "DIVERGENTE":
            o["divergente"] += valor
        else:
            o["conciliado"] += valor
    linhas = comum.ordenar(list(por_op.values()), "sem_retorno")
    for l in linhas:
        l["pct_sem_retorno"] = comum.pct(l["sem_retorno"], l["exportado"])
    campos = ["guias", "exportado", "guias_sem_retorno", "sem_retorno", "divergente", "conciliado"]
    total = {c: sum(l[c] for l in linhas) for c in campos}
    total["pct_sem_retorno"] = comum.pct(total["sem_retorno"], total["exportado"])
    tabela = comum.top_com_outros(linhas, "operadora", campos, 15)
    for l in tabela:
        if l.get("outros"):
            l["pct_sem_retorno"] = comum.pct(l["sem_retorno"], l["exportado"])
    topo = linhas[:10]
    resumo = resumo or {}
    return {
        "vazio": not guias,
        "sem_conciliacao": xml is None,
        "origens": origens,
        "planilha_referencia": resumo.get("planilha_referencia"),
        "linhas": tabela,
        "total": total,
        "arquivos": int(comum.num(resumo.get("arquivos"))),
        "ultimo": resumo.get("ultimo"),
        "grafico": comum.grafico(
            "barras-h",
            [l["operadora"] for l in topo],
            [{"nome": "Sem retorno", "tom": "coral", "valores": [l["sem_retorno"] for l in topo]},
             {"nome": "Conciliado", "tom": "teal", "valores": [l["conciliado"] + l["divergente"] for l in topo]}],
            empilhado=True,
        ),
        "altura": max(220, 34 * len(topo) + 50),
    }


def montar_amostra():
    import datetime

    guias = [{"id_conta": c, "id_admissao": a, "operadora": o, "faturavel": v}
             for c, a, o, v in [(1, 11, "Bradesco Saúde", 480_000), (1, 12, "Bradesco Saúde", 310_000),
                                (2, 21, "Amil", 260_000), (3, 31, "Cassi", 190_000), (3, 32, "Cassi", 75_000),
                                (4, 41, "SulAmérica", 140_000)]]
    xml = [{"id_conta": 3, "id_admissao": 31, "situacao": "CONCILIADO"},
           {"id_conta": 3, "id_admissao": 32, "situacao": "DIVERGENTE"}]
    planilha = [{"id_conta": 1, "id_admissao": 11, "id_paciente": 7, "situacao": "CONCILIADO"}]
    return montar(guias, xml, planilha, {"arquivos": 1, "ultimo": datetime.date(2026, 5, 19),
                                          "planilha_referencia": datetime.date(2026, 9, 18)})
