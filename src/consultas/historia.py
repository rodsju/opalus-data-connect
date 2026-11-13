"""História da conta: a mesma cascata do relatório de faturamento, mais exportação e retorno.

Bruto lançado → (−) pacote → (−) pré-auditoria → faturável → (−) particular →
fatura da operadora; exportado (sim/parcial/não) e o retorno da operadora (glosado,
sem glosa, sem retorno). A base é a linha da Conta do paciente (conta × admissão
× orçamento, sql_oracle '_CONTA_PACIENTE'); as consultas financeiras põem
COLUNAS nas suas listas e somam com agregar() -- uma conta só, números iguais.

A glosa vem por guia (conta × admissão): planilha/XML em cp_glosas (glosa_efetiva,
XML por cima da planilha), XML puro em tiss_retornos. Guia com mais de um
orçamento: glosa por item do XML quando há (id_item_erp → IDBUDGET); sem isso,
rateada pelo faturável de cada orçamento.
"""

import concurrent.futures

from ..reports import comum, fonte

LOTE = 900
EXPORTADA = "Exportada (fechada)"
SOMAS = ("bruto", "pacote", "pre_auditoria", "desconto_informativo", "faturamento_grupo", "particular",
         "fatura_operadora", "tributos_erp", "glosa_iw", "itens", "itens_pre_auditados", "exportado")
# Pior primeiro: na soma de várias guias vale o mais grave
RETORNOS = ("glosado", "sem retorno", "sem conciliação", "sem glosa", "não exportado")

# Retorno -> "teve glosa?". Onde a linha não é a guia (ex.: orçamento), o valor da glosa não se liga a
# ela -- o retorno é por guia (conta × admissão) -- e a lista mostra só isto.
GLOSADO = {"glosado": "sim", "sem glosa": "não", "sem retorno": "sem retorno", "não exportado": "não exportado",
           "sem conciliação": "sem conciliação"}

CASCATA = [
    {"campo": "bruto", "rotulo": "Bruto lançado", "formato": "moeda", "num": True},
    {"campo": "pacote", "rotulo": "(−) Pacote", "formato": "moeda", "num": True},
    {"campo": "pre_auditoria", "rotulo": "(−) Pré-auditoria", "formato": "moeda", "num": True},
    {"campo": "faturamento_grupo", "rotulo": "Faturável", "formato": "moeda", "num": True},
    {"campo": "particular", "rotulo": "(−) Particular", "formato": "moeda", "num": True},
    {"campo": "fatura_operadora", "rotulo": "Fatura operadora", "formato": "moeda", "num": True},
    {"campo": "exportado", "rotulo": "Exportado", "formato": "moeda", "num": True, "sub": "exportado_rotulo"},
]
COLUNA_GLOSA = {"campo": "glosa", "rotulo": "Retorno / glosa", "formato": "moeda", "num": True, "sub": "glosa_nota"}
COLUNA_GLOSADO = {"campo": "glosado", "rotulo": "Glosado", "formato": "badge"}
COLUNAS = [*CASCATA, COLUNA_GLOSA]


def lotes(nome, bind, valores):
    """fonte.rodar em lotes de 900 (teto do IN), em paralelo: cada lote abre a própria conexão."""
    lista = sorted(valores)
    partes = [lista[i:i + LOTE] for i in range(0, len(lista), LOTE)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        return [l for r in pool.map(lambda p: fonte.rodar(nome, {bind: p}), partes) for l in r]


def chave_glosa(l):
    return (l["id_conta"], "A", l["id_admissao"]) if l.get("id_admissao") else (l["id_conta"], "P", l["id_paciente"])


def retornos(contas):
    """{'glosas', 'xml', 'itens'} das contas, ou None se a Conciliação (Postgres) não respondeu."""
    if not contas:
        return {"glosas": {}, "xml": {}, "itens": {}}
    try:
        glosas = {chave_glosa(l): l for l in lotes("cp_glosas", "CONTAS", contas)}
        xml = {(r["id_conta"], r["id_admissao"]): r for r in lotes("tiss_retornos", "CONTAS", contas)}
        itens_xml = lotes("tiss_glosa_itens", "CONTAS", contas)
    except comum.ConsultaFalhou:
        return None
    itens = {}
    ids = {i["id_item_erp"] for i in itens_xml if i.get("id_item_erp")}
    try:
        orcamento = {r["id_item"]: r["id_orcamento"] for r in lotes("conta_paciente_itens_orcamento", "IDS", ids)}
    except comum.ConsultaFalhou:
        orcamento = {}  # sem o de-para do item, a guia cai no rateio
    for i in itens_xml:
        if i.get("id_item_erp") in orcamento:
            k = (i["id_conta"], i["id_admissao"], orcamento[i["id_item_erp"]])
            itens[k] = itens.get(k, 0) + comum.num(i["glosa"])
    return {"glosas": glosas, "xml": xml, "itens": itens}


def rotulo_origem(origem):
    partes = sorted(set((origem or "planilha").split("/")), key=lambda o: o != "xml")
    return f"({'/'.join(partes)})"


def repartir(total, partes):
    """total × cada parte, em centavos; o resto do arredondamento vai na maior parte -- a soma fecha."""
    valores = [round(total * p, 2) for p in partes]
    if valores and abs(sum(partes) - 1) < 1e-9:
        maior = max(range(len(partes)), key=lambda i: partes[i])
        valores[maior] = round(valores[maior] + total - sum(valores), 2)
    return valores


def marcar(linhas, ret):
    """Acrescenta exportado, glosa (rateada entre orçamentos da guia) e retorno a cada linha. Puro.

    ret: retornos() -- None = Conciliação indisponível ('sem conciliação', glosa vazia).
    """
    guias, usadas = {}, set()
    for l in linhas:
        guias.setdefault((l["id_conta"], l["id_admissao"]), []).append(l)
    for (conta, adm), grupo in guias.items():
        exportada = grupo[0].get("situacao") == EXPORTADA
        g = xml = None
        if ret is not None:
            xml = ret["xml"].get((conta, adm))
            for k in ((conta, "A", adm), (conta, "P", grupo[0].get("id_paciente"))):
                if k in ret["glosas"] and k not in usadas:  # casada pelo paciente: uma guia só
                    g = ret["glosas"][k]
                    usadas.add(k)
                    break
        total = comum.num(g["glosa"]) if g else comum.num(xml["glosa"]) if xml else 0
        faturavel = sum(comum.num(l.get("faturamento_grupo")) for l in grupo)
        por_item = {l.get("id_orcamento"): ret["itens"].get((conta, adm, l.get("id_orcamento")))
                    for l in grupo} if ret else {}
        exato = len(grupo) == 1 or any(v is not None for v in por_item.values())
        tem_retorno = g is not None or xml is not None
        if ret is None:
            retorno = "sem conciliação" if exportada else "não exportado"
        elif total > 0:
            retorno = "glosado"
        elif tem_retorno:
            retorno = "sem glosa"
        else:
            retorno = "sem retorno" if exportada else "não exportado"
        rateada = total > 0 and not exato
        origem = (g.get("origem_glosa") or "planilha") if g else ("xml" if xml else None)
        nota = " ".join(p for p in (retorno, rotulo_origem(origem) if origem else None,
                                    g.get("motivos") if g and total > 0 else None,
                                    f"· rateada pelo faturável ({len(grupo)} linhas)" if rateada else None) if p)
        if len(grupo) == 1:
            partes = [1.0]
        elif exato:
            partes = [comum.num(por_item.get(l.get("id_orcamento"))) / total if total else 0.0 for l in grupo]
        else:
            partes = [comum.num(l.get("faturamento_grupo")) / faturavel if faturavel else 1 / len(grupo)
                      for l in grupo]
        glosas = repartir(total, partes)
        recuperados = repartir(comum.num(g["recuperado"]), partes) if g else [None] * len(grupo)
        perdas = repartir(comum.num(g["perda"]), partes) if g else [None] * len(grupo)
        for l, glosa, recuperado, perda in zip(grupo, glosas, recuperados, perdas):
            l.update({
                "exportado": comum.num(l.get("faturamento_grupo")) if exportada else 0.0,
                "exportado_rotulo": "sim" if exportada else "não",
                "glosa": glosa if tem_retorno else None,
                "recuperado": recuperado,
                "perda": perda,
                "glosa_rateada": rateada,
                "retorno": retorno,
                "origem_glosa": origem,
                "motivos": g.get("motivos") if g else None,
                "status_glosa": g.get("status_glosa") if g else None,
                "situacao_cruzamento": g.get("situacao_cruzamento") if g else None,
                "faturado_planilha": comum.num(g["faturado_planilha"]) if g else None,
                "glosa_nota": nota,
            })
    return linhas


def rotulo_exportado(faturavel, exportado):
    if faturavel <= 0.005:
        return "—"
    if exportado >= faturavel - 1:
        return "sim"
    return "não" if exportado <= 0.005 else "parcial"


def vazia():
    """História de quem ainda não tem conta (orçamento não faturado)."""
    return {**{k: 0.0 for k in SOMAS}, "glosa": None, "recuperado": None, "perda": None, "a_exportar": 0.0,
            "retorno": None, "glosado": None, "exportado_rotulo": "—", "glosa_rateada": False,
            "glosa_nota": "sem conta"}


def agregar(linhas, chave):
    """Linhas marcadas -> {valor da chave: somas da história}. Puro. Retorno: o pior entre as linhas."""
    saida = {}
    for l in linhas:
        g = saida.get(l[chave])
        if g is None:
            g = saida[l[chave]] = {**{k: 0.0 for k in SOMAS}, "glosa": None, "recuperado": None, "perda": None,
                                   "_retornos": set(), "_rateada": False}
        for k in SOMAS:
            g[k] += comum.num(l.get(k))
        for k in ("glosa", "recuperado", "perda"):
            if l.get(k) is not None:
                g[k] = (g[k] or 0) + l[k]
        g["_retornos"].add(l.get("retorno"))
        g["_rateada"] |= bool(l.get("glosa_rateada"))
    for g in saida.values():
        retorno = next((r for r in RETORNOS if r in g["_retornos"]), None)
        g.update(a_exportar=round(g["faturamento_grupo"] - g["exportado"], 2), retorno=retorno,
                 glosado=GLOSADO.get(retorno),
                 exportado_rotulo=rotulo_exportado(g["faturamento_grupo"], g["exportado"]),
                 glosa_rateada=g["_rateada"],
                 glosa_nota=" ".join(p for p in (retorno, "rateada" if g["_rateada"] else None) if p))
        del g["_retornos"], g["_rateada"]
    return saida
