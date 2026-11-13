"""Consultas › Orçamentos: lista filtrada -> tríade orçamento × fatura × glosa -> análise por IA.

Orçamento, itens e fatura vêm do Oracle (sql_oracle, 'orcamento*'); a glosa vem
da planilha, pela admissão casada no cruzamento e pela competência; o risco da
lista é por regras (orcamento_risco), a IA só roda sob demanda (orcamento_ia).
Paciente aparece só pelo código ('P' + ID do ERP).
"""

import concurrent.futures
import datetime
import logging

from .. import catalogo, ia, layout, provedores
from ..conciliacao import banco
from ..reports import comum, fonte, orcamento_ia, orcamento_risco
from . import historia, lista

logger = logging.getLogger(__name__)

FOCOS = {
    "prevenir": "A prevenir (conta ainda não exportada)",
    "com_glosa": "Glosados (retorno da operadora)",
    "faturados": "Faturados (contas exportadas)",
    "todos": "Todos",
}


def _codigo(id_paciente):
    return f"P{id_paciente}" if id_paciente else None


def _mes(data):
    data = data.date() if isinstance(data, datetime.datetime) else data
    return data.replace(day=1) if data else None


def _depois(mes):
    return (mes.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)


def _datas(orc):
    """Oracle devolve DATE como datetime à meia-noite: na tela é só data."""
    return {**orc, **{k: _mes_dia(orc.get(k)) for k in ("inicio", "fim", "validade_senha")}}


def _mes_dia(valor):
    return valor.date() if isinstance(valor, datetime.datetime) else valor


_cache_taxas = {"expira": 0, "dados": {}}


def taxas_operadora():
    """{operadora: {taxa, motivo}} dos últimos 12 meses: glosa (planilha) ÷ fatura da operadora (Oracle).

    Guardado 1 h no processo: a fatura por operadora em 12 meses custa ~1,6 s no Oracle.
    """
    import time

    if _cache_taxas["expira"] > time.time():
        return _cache_taxas["dados"]
    fim = datetime.date.today().replace(day=1)
    inicio = fim.replace(year=fim.year - 1)
    periodo = {"DT_INI": inicio, "DT_FIM": fim, "UNIDADE": None, "TIPO": None}
    fatura = {l["grupo"]: comum.num(l["fatura_operadora"]) for l in _pg("cascata_por_operadora", periodo, [])}
    glosa = _pg("orc_glosa_operadora", periodo, [])
    dados = {g["operadora"]: {"taxa": comum.pct(g["glosa"], fatura.get(g["operadora"])), "motivo": g["motivo"]}
             for g in glosa if fatura.get(g["operadora"])}
    if fatura:  # só guarda se o Oracle respondeu
        _cache_taxas.update(expira=time.time() + 3600, dados=dados)
    return dados


def _pg(nome, params, padrao):
    try:
        return fonte.rodar(nome, params)
    except comum.ConsultaFalhou:
        logger.exception("orcamentos: %s indisponível", nome)
        return padrao


# --------------------------------------------------------------------------
# Lista
# --------------------------------------------------------------------------


def historia_orcamentos(ids):
    """{id_orcamento: história da conta} somando as guias (conta × admissão) que faturam cada orçamento.

    inicio_aberta: competência mais recente de conta com faturável ainda não exportado (regra da senha).
    """
    if not ids:
        return {}
    guias = {(g["id_conta"], g["id_admissao"]) for g in historia.lotes("guias_por_orcamento", "IDS", ids)}
    linhas = [l for l in historia.lotes("conta_paciente_por_conta", "IDS", {c for c, _ in guias})
              if (l["id_conta"], l["id_admissao"]) in guias]
    historia.marcar(linhas, historia.retornos({l["id_conta"] for l in linhas}))
    saida = historia.agregar(linhas, "id_orcamento")
    for l in linhas:
        if l.get("situacao") != historia.EXPORTADA and comum.num(l.get("faturamento_grupo")) > 0:
            h, inicio = saida[l["id_orcamento"]], _mes_dia(l.get("competencia"))
            h["inicio_aberta"] = max(h.get("inicio_aberta") or inicio, inicio)
    return saida


def com_historia(orc, h):
    """Orçamento + a história dele. 'faturado' passa a ser o faturável da história (o do relatório)."""
    h = h or historia.vazia()
    validade, inicio = orc.get("validade_senha"), h.get("inicio_aberta")
    return {**orc, **h, "faturado": h["faturamento_grupo"],
            "aberta_apos_validade": bool(validade and inicio and inicio > validade)}


def criterio_senha():
    """Premissas › Parâmetros gerais. Sem banco ou valor desconhecido: o padrão (período atendido)."""
    try:
        linhas = banco.consultar("SELECT valor FROM conciliacao.parametro WHERE chave = %s",
                                 ("criterio_senha_vencida",), "critério da senha vencida")
    except catalogo.ConsultaFalhou:
        return orcamento_risco.PERIODO_ATENDIDO
    valor = (linhas[0]["valor"] or "").strip() if linhas else ""
    return valor if valor in (orcamento_risco.PERIODO_ATENDIDO, orcamento_risco.DATA_ENVIO) \
        else orcamento_risco.PERIODO_ATENDIDO


def montar_lista(orcamentos, historias, taxas, pacientes, analisados, foco, operadora="", busca="", hoje=None,
                 criterio=orcamento_risco.PERIODO_ATENDIDO):
    """Puro: linhas do Oracle + história da conta de cada orçamento -> linhas da tela e KPIs."""
    busca = (busca or "").strip().upper()
    saida = []
    for o in map(_datas, orcamentos):
        if operadora and o["operadora"] != operadora:
            continue
        codigo = _codigo(o["id_paciente"])
        if busca and busca not in (str(o["id_orcamento"]), str(o.get("id_paciente")), (codigo or "").upper()):
            continue
        o = com_historia(o, historias.get(o["id_orcamento"]))
        linha = {**o, "paciente_codigo": codigo,
                 "diferenca": comum.num(o["faturamento_grupo"]) - comum.num(o["orcado"]),
                 "analisado": o["id_orcamento"] in analisados}
        cancelado = o["situacao"] == "Cancelado"
        # A prevenir: ainda há faturável por exportar, ou nada foi exportado. Conta aberta com R$ 0 não conta.
        aberto = o["a_exportar"] > 1 or o["retorno"] in (None, "não exportado")
        # Busca por número/paciente acha em qualquer foco
        if not busca and foco == "prevenir" and (cancelado or not aberto):
            continue
        if not busca and foco == "faturados" and aberto:
            continue
        if not busca and foco == "com_glosa" and o["glosado"] != "sim":
            continue
        linha["riscos"] = orcamento_risco.avaliar(o, taxas, pacientes, hoje, criterio)
        linha["nivel"] = orcamento_risco.nivel(linha["riscos"])
        saida.append(linha)
    saida.sort(key=lambda l: (-orcamento_risco.PESO.get(l["nivel"], 0), -comum.num(l["faturado"])))
    return {"linhas": saida, "total": len(saida), "kpis": resumo(saida, foco),
            "operadoras": sorted({o["operadora"] for o in orcamentos})}


def resumo(saida, foco=""):
    soma = lambda c: sum(comum.num(l[c]) for l in saida)  # noqa: E731
    return [
        {"rotulo": "Orçamentos", "valor": len(saida), "formato": "int", "icone": "clipboard-list", "tom": "blue",
         "hint": FOCOS.get(foco, "")},
        {"rotulo": "Orçado", "valor": soma("orcado"), "formato": "moeda_curta", "icone": "wallet", "tom": "violet",
         "hint": "preço × (qtd − qtd coberta)"},
        {"rotulo": "Faturável", "valor": soma("faturado"), "formato": "moeda_curta", "icone": "receipt", "tom": "cyan",
         "hint": f"a exportar {layout.fmt_moeda_curta(soma('a_exportar'))} · "
                 f"diferença {layout.fmt_moeda_curta(soma('diferenca'))}"},
        {"rotulo": "Risco alto", "valor": sum(1 for l in saida if l["nivel"] == "alta"), "formato": "int",
         "icone": "triangle-alert", "tom": "coral", "barra": comum.pct(sum(1 for l in saida if l["nivel"] == "alta"),
                                                                       len(saida)), "hint": "por regras, sem IA"},
        {"rotulo": "Glosados", "valor": sum(1 for l in saida if l["glosado"] == "sim"), "formato": "int",
         "icone": "shield-x", "tom": "magenta",
         "hint": f"{sum(1 for l in saida if l['glosado'] == 'sem retorno')} sem retorno da operadora"},
    ]


def carregar(f):
    """Filtros da consulta -> linhas com risco (motor de src/consultas/lista.py)."""
    foco = f.get("foco") if f.get("foco") in FOCOS else "prevenir"
    mes = f.get("mes") or datetime.date.today().strftime("%Y-%m")
    filtros = comum.Filtros(mes, f.get("unidade"), tipo=f.get("tipo"))
    orcamentos = fonte.rodar("orcamentos_lista", filtros.params())
    ids = {o["id_orcamento"] for o in orcamentos}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        f_hist = pool.submit(historia_orcamentos, ids)
        f_taxas = pool.submit(taxas_operadora)
        f_pac = pool.submit(_pg, "orc_pacientes_glosados", {}, [])
        historias, taxas, pacientes = f_hist.result(), f_taxas.result(), f_pac.result()
    try:
        analisados = {l["id_orcamento"] for l in banco.consultar(
            "SELECT DISTINCT id_orcamento FROM conciliacao.analise_orcamento WHERE id_orcamento = ANY(%s)",
            (sorted(ids),), "orçamentos analisados")}
    except catalogo.ConsultaFalhou:
        analisados = set()
    linhas = montar_lista(orcamentos, historias, taxas, {p["id_paciente"] for p in pacientes}, analisados,
                          foco, f.get("operadora"), f.get("busca"), criterio=criterio_senha())["linhas"]
    for l in linhas:
        l["nivel_ordem"] = orcamento_risco.PESO.get(l["nivel"], 0)
        l["por_que"] = " · ".join(r["texto"] for r in l["riscos"][:2])
    return linhas


def _unidades_provider(_f):
    try:
        return [(u["unidade_negocio"], u["unidade_negocio"]) for u in fonte.rodar("unidades_canonicas", {})
                if u.get("unidade_negocio")]
    except comum.ConsultaFalhou:
        return []


CONSULTA = {
    "slug": "orcamentos", "titulo": "Orçamentos", "icone": "clipboard-check",
    "descricao": "Cada orçamento em tríade com a fatura e a glosa, com risco por regras. Por padrão, os que ainda "
                 "dá para corrigir antes de a conta ir para a operadora. Abra um para ver item a item e pedir a "
                 "análise por IA.",
    "filtros": [
        {"nome": "mes", "rotulo": "Início do orçamento", "tipo": "mes"},
        {"nome": "foco", "rotulo": "Foco", "tipo": "select", "opcoes": list(FOCOS.items()), "padrao": "prevenir",
         "sem_vazio": True},
        {"nome": "unidade", "rotulo": "Unidade (provider)", "tipo": "select", "opcoes": _unidades_provider},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select",
         "opcoes": [("0", "Hospital de transição"), ("1", "Home care"), ("3", "Ambulatorial")]},
        {"nome": "operadora", "rotulo": "Operadora", "tipo": "texto"},
        {"nome": "busca", "rotulo": "Nº, ID ou código do paciente", "tipo": "texto"},
    ],
    "colunas": [
        {"campo": "nivel_ordem", "rotulo": "Risco", "formato": "risco"},
        {"campo": "id_orcamento", "rotulo": "Orçamento", "formato": "mono", "link": "/consultas/orcamentos/{id_orcamento}"},
        {"campo": "id_paciente", "rotulo": "ID paciente (Oracle)", "formato": "mono"},
        {"campo": "paciente_codigo", "rotulo": "Código", "formato": "codigo_paciente"},
        {"campo": "paciente_codigo", "rotulo": "Nome", "formato": "nome_paciente", "so_tela": True},
        {"campo": "unidade", "rotulo": "Unidade", "sub": "operadora"},
        {"campo": "inicio", "rotulo": "Início", "formato": "data", "sub": "fim"},
        {"campo": "situacao", "rotulo": "Situação"},
        {"campo": "orcado", "rotulo": "Orçado", "formato": "moeda", "num": True},
        *historia.CASCATA,
        historia.COLUNA_GLOSADO,
        {"campo": "diferenca", "rotulo": "Faturável − orçado", "formato": "moeda", "num": True},
        {"campo": "por_que", "rotulo": "Por quê", "formato": "texto_longo"},
        {"campo": "nivel", "rotulo": "Nível de risco", "so_csv": True},
        {"campo": "operadora", "rotulo": "Operadora", "so_csv": True},
        {"campo": "fim", "rotulo": "Fim", "formato": "data", "so_csv": True},
        {"campo": "a_exportar", "rotulo": "Faturável a exportar", "so_csv": True},
        {"campo": "retorno", "rotulo": "Retorno da operadora", "so_csv": True},
        {"campo": "validade_senha", "rotulo": "Validade da senha", "formato": "data", "so_csv": True},
    ],
    "carregar": carregar,
    "resumo": lambda linhas: resumo(linhas),
}


# --------------------------------------------------------------------------
# Detalhe
# --------------------------------------------------------------------------


def montar_contexto(id_orcamento):
    """Tudo o que o detalhe e a IA precisam. None se o orçamento não existe."""
    p = {"ID": id_orcamento}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futuros = {n: pool.submit(fonte.rodar, n, p) for n in
                   ("orcamento_cabecalho", "orcamento_itens", "orcamento_faturado_itens", "orcamento_contas")}
        dados = {n: f.result() for n, f in futuros.items()}
    if not dados["orcamento_cabecalho"]:
        return None
    orc = _datas(dados["orcamento_cabecalho"][0])
    orc = com_historia(orc, historia_orcamentos({id_orcamento}).get(id_orcamento))
    ini, fim = _mes(orc["inicio"]), _depois(_mes(orc["fim"]))
    glosas = _pg("orc_glosa_linhas", {"ADMISSAO": orc["id_admissao"], "DT_INI": ini, "DT_FIM": fim}, [])
    historico = _pg("orc_hist_operadora", {"OPERADORA": orc["operadora"]}, [])
    taxas = taxas_operadora()
    pacientes = {x["id_paciente"] for x in _pg("orc_pacientes_glosados", {}, [])}
    comparacao = orcamento_risco.comparar_itens(dados["orcamento_itens"], dados["orcamento_faturado_itens"])
    riscos = orcamento_risco.avaliar(orc, taxas, pacientes, criterio=criterio_senha()) + \
        orcamento_risco.avaliar_itens(comparacao)
    itens = dados["orcamento_itens"]
    categorias = {}
    for i in itens:
        c = categorias.setdefault(i["categoria"], {"categoria": i["categoria"], "itens": 0, "cobrado": 0.0})
        c["itens"] += 1
        c["cobrado"] += comum.num(i["cobrado"])
    soma = lambda c: sum(comum.num(i[c]) for i in itens)  # noqa: E731
    return {
        "orcamento": orc, "paciente_codigo": _codigo(orc["id_paciente"]), "itens": itens,
        "categorias": sorted(categorias.values(), key=lambda c: -c["cobrado"]),
        "cascata": comum.cascata([
            ("Bruto orçado", soma("bruto"), "total", "tudo o que foi orçado, a preço de tabela"),
            ("Incluso em pacote", soma("pacote"), "neg", "coberto por diária/pacote"),
            ("Orçado cobrável", soma("cobrado"), "total", "o que pode virar fatura"),
        ]),
        "comparacao": comparacao, "glosas": glosas,
        "contas": [{**c, **{k: _mes_dia(c.get(k)) for k in ("inicio", "fim", "data_entrega")}}
                   for c in dados["orcamento_contas"]],
        "historico_operadora": historico, "riscos": riscos, "nivel": orcamento_risco.nivel(riscos),
        "resumo_desvios": {t: sum(1 for c in comparacao if c["tipo"] == t) for t in
                           ("igual", "faturado sem orçar", "qtd acima", "preço diferente", "qtd abaixo",
                            "orçado não faturado")},
    }


def gerar_detalhe(usuario, id_orcamento, aviso=None, erro=None):
    try:
        ctx = montar_contexto(id_orcamento)
    except comum.ConsultaFalhou as falha:
        ctx, erro = None, {"motivo": falha.motivo, "detalhe": falha.dica}
    if ctx is None and not erro:
        return None, 404
    analise = None
    if ctx:
        try:
            analise = orcamento_ia.ultima(id_orcamento)
        except catalogo.ConsultaFalhou:
            analise = None
    try:
        provedor = provedores.escolher().rotulo
    except provedores.ConfiguracaoInvalida:
        provedor = None
    html = layout.render(
        "consultas/orcamento_detalhe.html", f"Orçamento {id_orcamento}", usuario, "/consultas/orcamentos",
        ctx=ctx, id_orcamento=id_orcamento, analise=analise, provedor=provedor, aviso=aviso, erro=erro,
        consultas=lista.CONSULTAS_MENU)
    return html, 200


def analisar(id_orcamento, autor, forcar=False):
    """(aviso, erro) da análise por IA do orçamento."""
    try:
        ctx = montar_contexto(id_orcamento)
        if ctx is None:
            return None, {"motivo": "orçamento não encontrado", "detalhe": str(id_orcamento)}
        registro, reaproveitada = orcamento_ia.analisar(ctx, autor=autor, forcar=forcar)
    except comum.ConsultaFalhou as falha:
        return None, {"motivo": falha.motivo, "detalhe": falha.dica}
    except provedores.ConfiguracaoInvalida as falha:
        return None, {"motivo": str(falha), "detalhe": "Cadastre um provedor em Setup › AI Providers."}
    except ia.GeracaoFalhou as falha:
        return None, {"motivo": falha.motivo, "detalhe": getattr(falha, "detalhe", "")}
    n = len((registro["resultado"] or {}).get("riscos", []))
    if reaproveitada:
        return f"Nada mudou desde a última análise ({n} riscos): reaproveitada sem nova chamada à IA.", None
    return f"Análise concluída por {registro['modelo']}: {n} riscos apontados.", None
