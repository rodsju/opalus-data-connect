"""Consultas › Conta do paciente: orçamento → pré-auditoria → fatura → glosa numa linha só.

Uma linha por conta × admissão × orçamento. A conta de lote junta vários
pacientes, e uma mesma conta pode faturar mais de um orçamento do paciente
(períodos em sequência, os dois autorizados); cada item faturado aponta para um
orçamento só (IDBUDGET), e os itens sem orçamento formam a própria linha.

A glosa vem da carga ativa da planilha, casada por admissão da conta
(conciliacao.cruzamento). A planilha não separa por orçamento: a glosa do
paciente na conta entra UMA vez, na primeira linha dele. Tudo o mais é Oracle.
"""

from .. import layout
from ..reports import comum, fonte

LOTE = 900
TIPOS = [(k, v) for k, v in comum.Filtros.TIPOS.items() if k]


def _unidades(_filtros):
    try:
        return [(l["unidade"].strip(), l["unidade"].strip()) for l in fonte.rodar("unidades_faturam", {})
                if l.get("unidade")]
    except comum.ConsultaFalhou:
        return []


def _valores_orcamento(ids):
    saida = {}
    lista = sorted(ids)
    for inicio in range(0, len(lista), LOTE):
        for l in fonte.rodar("orcamentos_valor", {"IDS": lista[inicio:inicio + LOTE]}):
            saida[l["id_orcamento"]] = l
    return saida


def _glosas(contas):
    """{(conta, 'A', admissão) | (conta, 'P', paciente): glosa agregada}. Vazio sem carga ou sem Postgres."""
    if not contas:
        return {}
    try:
        linhas = fonte.rodar("cp_glosas", {"CONTAS": sorted(contas)})
    except comum.ConsultaFalhou:
        return {}
    saida = {}
    for l in linhas:
        chave = (l["id_conta"], "A", l["id_admissao"]) if l["id_admissao"] else (l["id_conta"], "P", l["id_paciente"])
        saida[chave] = l
    return saida


def _data(valor):
    return valor.date() if hasattr(valor, "date") else valor


def _periodo(orc):
    ini, fim = _data(orc.get("orcamento_inicio")), _data(orc.get("orcamento_fim"))
    if not ini:
        return orc["situacao_orcamento"]
    return f"{ini:%d/%m} a {fim:%d/%m} · {orc['situacao_orcamento']}" if fim else orc["situacao_orcamento"]


def nota_fiscal(c, notas_planilha):
    """(número, origem) da nota da conta: ERP (BSNUMBER/série), documento financeiro numérico, ou planilha."""
    if c.get("nf_numero"):
        serie = c.get("nf_serie")
        return (f"{c['nf_numero']}" + (f" / série {serie}" if serie else "")), "ERP"
    doc = (c.get("doc_financeiro") or "").strip()
    if doc.isdigit() and doc.strip("0"):
        return doc.lstrip("0"), "ERP (doc. financeiro)"
    if notas_planilha:
        return ", ".join(sorted(notas_planilha)), "planilha"
    return None, None


def _rotulo_origem(glosa):
    partes = sorted(set((glosa.get("origem_glosa") or "planilha").split("/")), key=lambda o: o != "xml")
    return f"({'/'.join(partes)})"


def juntar(contas, orcamentos, glosas):
    """Linhas do Oracle (conta × admissão × orçamento) + orçamentos + glosa da planilha. Puro."""
    por_admissao = {}
    for c in contas:
        if c.get("id_orcamento"):
            por_admissao.setdefault((c["id_conta"], c["id_admissao"]), []).append(c["id_orcamento"])
    notas = {}
    for (conta, _, _), g in glosas.items():
        notas.setdefault(conta, set()).update(n.strip() for n in (g.get("notas_planilha") or "").split(",") if n.strip())
    usadas = set()
    saida = []
    for c in contas:
        nf, nf_origem = nota_fiscal(c, notas.get(c["id_conta"]))
        orc = orcamentos.get(c.get("id_orcamento")) if c.get("id_orcamento") else None
        # Glosa: uma vez por admissão da conta; casada pelo total do paciente, uma vez por paciente
        chave = (c["id_conta"], "A", c["id_admissao"])
        glosa = glosas.get(chave)
        if glosa is None:
            chave = (c["id_conta"], "P", c.get("id_paciente"))
            glosa = glosas.get(chave)
        do_paciente = glosa  # vale para os filtros em todas as linhas do paciente
        if glosa is not None and chave in usadas:
            glosa = None
        if glosa is not None:
            usadas.add(chave)
        irmaos = por_admissao.get((c["id_conta"], c["id_admissao"]), [])
        orcado = comum.num(orc["orcado"]) if orc else None
        saida.append({
            **c,
            "competencia": _data(c.get("competencia")),
            "nota_fiscal": nf, "nf_origem": nf_origem,
            "detalhe": f"/consultas/conta-paciente/{c['id_conta']}/{c['id_admissao'] or 0}/{c.get('id_orcamento') or 0}",
            "tipo_nome": comum.Filtros.TIPOS.get(str(c.get("tipo")), "") if c.get("tipo") is not None else "",
            "orcamento_rotulo": (_periodo(orc) if orc else
                                 ("orçamento não encontrado" if c.get("id_orcamento") else "itens sem orçamento")),
            "situacao_orcamento": orc["situacao_orcamento"] if orc else None,
            "orcamento_inicio": _data(orc.get("orcamento_inicio")) if orc else None,
            "orcamento_fim": _data(orc.get("orcamento_fim")) if orc else None,
            "orcamentos_na_conta": len(irmaos),
            "orcado": orcado,
            "dif_orcado": (comum.num(c["faturamento_grupo"]) - orcado) if orcado is not None else None,
            "glosa": comum.num(glosa["glosa"]) if glosa else None,
            "origem_glosa": glosa.get("origem_glosa") if glosa else None,
            "glosa_nota": (f"{_rotulo_origem(glosa)} " + ("do paciente na conta (todos os orçamentos)"
                                                          if len(irmaos) > 1 else (glosa["motivos"] or ""))).strip()
            if glosa else None,
            "recuperado": comum.num(glosa["recuperado"]) if glosa else None,
            "perda": comum.num(glosa["perda"]) if glosa else None,
            "faturado_planilha": comum.num(glosa["faturado_planilha"]) if glosa else None,
            "motivos": glosa["motivos"] if glosa else None,
            "status_glosa": glosa["status_glosa"] if glosa else None,
            "situacao_cruzamento": glosa["situacao_cruzamento"] if glosa else None,
            "_glosa": comum.num(do_paciente["glosa"]) if do_paciente else 0,
            "_recuperado": comum.num(do_paciente["recuperado"]) if do_paciente else 0,
            "_perda": comum.num(do_paciente["perda"]) if do_paciente else 0,
        })
    return saida


SITUACOES_ORCAMENTO = ["Autorizado (operadora)", "Autorizado (interno)", "Liberado", "Pendente", "Cancelado"]
COM_SEM = [("com", "Com valor"), ("sem", "Sem valor")]
DESFECHOS = [("recuperado", "Com recuperação"), ("perda", "Com perda"), ("ambos", "Recuperação e perda"),
             ("aberto", "Sem recuperação nem perda")]
DESTAQUES = [("acima", "Faturado acima do orçado"), ("varios", "Mais de um orçamento do paciente na conta")]


def _com_sem(valor, escolha):
    return not escolha or (escolha == "com") == (comum.num(valor) > 0)


def _passa(l, f):
    """Filtros de valor/situação sobre uma linha já montada. f: dict do GET."""
    orc = f.get("orcamento")
    if orc == "sem" and l.get("id_orcamento"):
        return False
    if orc and orc != "sem" and l.get("situacao_orcamento") != orc:
        return False
    if f.get("fatura") and l.get("situacao") != f["fatura"]:
        return False
    if not _com_sem(l.get("pre_auditoria"), f.get("pre")) or not _com_sem(l.get("desconto_informativo"),
                                                                            f.get("desconto")):
        return False
    # Glosa, recuperação e perda são do paciente na conta: valem para todas as linhas dele
    if not _com_sem(l["_glosa"], f.get("glosa")):
        return False
    desfecho = f.get("desfecho")
    rec, perda = l["_recuperado"] > 0, l["_perda"] > 0
    if desfecho == "recuperado" and not rec or desfecho == "perda" and not perda:
        return False
    if desfecho == "ambos" and not (rec and perda) or desfecho == "aberto" and (not l["_glosa"] or rec or perda):
        return False
    destaque = f.get("destaque")
    if destaque == "acima" and not (l["dif_orcado"] is not None and l["dif_orcado"] > 1):
        return False
    if destaque == "varios" and l["orcamentos_na_conta"] <= 1:
        return False
    return True


def carregar(f):
    filtros = comum.Filtros(f.get("mes") or comum.mes_padrao(), f.get("unidade"), tipo=f.get("tipo"))
    contas = fonte.rodar("conta_paciente", filtros.params())
    ids = {c["id_orcamento"] for c in contas if c.get("id_orcamento")}
    linhas = juntar(contas, _valores_orcamento(ids), _glosas({c["id_conta"] for c in contas}))
    operadora = (f.get("operadora") or "").strip().upper()
    paciente = (f.get("paciente") or "").strip().upper().removeprefix("P")
    busca = (f.get("busca") or "").strip().upper()
    nf = (f.get("nf") or "").strip().lstrip("0")
    saida = []
    for l in linhas:
        if not _passa(l, f):
            continue
        if nf == "-" and l.get("nota_fiscal") or nf not in ("", "-") and nf not in (l.get("nota_fiscal") or ""):
            continue
        if operadora and operadora not in (l.get("operadora") or "").upper():
            continue
        if paciente and paciente != str(l.get("id_paciente")):
            continue
        if busca and busca not in {str(l["id_conta"]), (l.get("protocolo") or "").upper(), str(l.get("id_admissao")),
                                   str(l.get("id_orcamento"))}:
            continue
        saida.append(l)
    return saida


def resumo(linhas):
    # Orçamento faturado em mais de uma conta conta uma vez só
    orcado = {l["id_orcamento"]: l["orcado"] for l in linhas if l.get("id_orcamento") and l["orcado"] is not None}
    soma = lambda c: sum(comum.num(l.get(c)) for l in linhas)  # noqa: E731
    return [
        {"rotulo": "Orçado", "valor": sum(orcado.values()), "formato": "moeda_curta", "icone": "clipboard-check",
         "tom": "cyan", "hint": f"{len(orcado)} orçamentos · {len(linhas)} linhas"},
        {"rotulo": "Faturamento", "valor": soma("faturamento_grupo"), "formato": "moeda_curta", "icone": "banknote",
         "tom": "blue", "hint": f"bruto {layout.fmt_moeda_curta(soma('bruto'))}"},
        {"rotulo": "Pré-auditoria", "valor": soma("pre_auditoria"), "formato": "moeda_curta", "icone": "scan-search",
         "tom": "violet", "hint": "cortado antes do envio"},
        {"rotulo": "Fatura operadora", "valor": soma("fatura_operadora"), "formato": "moeda_curta",
         "icone": "building-2", "tom": "teal"},
        {"rotulo": "Glosa", "valor": soma("glosa"), "formato": "moeda_curta", "icone": "shield-x",
         "tom": "coral", "hint": f"perda {layout.fmt_moeda_curta(soma('perda'))}"},
    ]


CONSULTA = {
    "slug": "conta-paciente", "titulo": "Conta do paciente", "icone": "file-stack", "larga": True,
    "descricao": "A história de cada paciente dentro da conta: orçamento, pré-auditoria, fatura (bruto, pacote, "
                 "desconto, faturamento, fatura da operadora) e a glosa (XML da operadora ou planilha). Uma linha por conta × paciente × "
                 "orçamento — a conta pode faturar mais de um orçamento; a glosa do paciente entra na primeira linha.",
    "filtros": [
        {"nome": "mes", "rotulo": "Competência da conta", "tipo": "mes", "padrao": ""},
        {"nome": "unidade", "rotulo": "Unidade", "tipo": "select", "opcoes": _unidades},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select", "opcoes": TIPOS},
        {"nome": "operadora", "rotulo": "Operadora (contém)", "tipo": "texto"},
        {"nome": "paciente", "rotulo": "ID ou código do paciente", "tipo": "texto"},
        {"nome": "busca", "rotulo": "Conta, protocolo, orçamento ou IdAdm", "tipo": "texto"},
        {"nome": "nf", "rotulo": "Nota fiscal (\"-\" = sem nota)", "tipo": "texto"},
        {"nome": "orcamento", "rotulo": "Status do orçamento", "tipo": "select",
         "opcoes": [(s_, s_) for s_ in SITUACOES_ORCAMENTO] + [("sem", "Sem orçamento")]},
        {"nome": "fatura", "rotulo": "Status da fatura", "tipo": "select",
         "opcoes": [(s_, s_) for s_, _ in comum.SITUACOES_CONTA if s_ != "Simulação"]},
        {"nome": "pre", "rotulo": "Pré-auditoria", "tipo": "select", "opcoes": COM_SEM},
        {"nome": "desconto", "rotulo": "Desconto", "tipo": "select", "opcoes": COM_SEM},
        {"nome": "glosa", "rotulo": "Glosa", "tipo": "select", "opcoes": [("com", "Com glosa"),
                                                                                  ("sem", "Sem glosa")]},
        {"nome": "desfecho", "rotulo": "Recuperação e perda", "tipo": "select", "opcoes": DESFECHOS},
        {"nome": "destaque", "rotulo": "Destaque", "tipo": "select", "opcoes": DESTAQUES},
    ],
    "colunas": [
        {"campo": "competencia", "rotulo": "Comp.", "formato": "data"},
        {"campo": "id_conta", "rotulo": "Conta", "formato": "mono", "sub": "protocolo", "link": "{detalhe}"},
        {"campo": "nota_fiscal", "rotulo": "Nota fiscal", "formato": "mono", "sub": "nf_origem"},
        {"campo": "operadora", "rotulo": "Operadora", "sub": "unidade"},
        {"campo": "id_paciente", "rotulo": "ID paciente (Oracle)", "formato": "mono"},
        {"campo": "paciente_codigo", "rotulo": "Código", "formato": "codigo_paciente"},
        {"campo": "paciente_codigo", "rotulo": "Nome", "formato": "nome_paciente", "so_tela": True},
        {"campo": "id_orcamento", "rotulo": "Orçamento", "formato": "mono", "sub": "orcamento_rotulo",
         "link": "/consultas/orcamentos/{id_orcamento}"},
        {"campo": "orcado", "rotulo": "Orçado", "formato": "moeda", "num": True},
        {"campo": "bruto", "rotulo": "Bruto", "formato": "moeda", "num": True},
        {"campo": "pacote", "rotulo": "Pacote", "formato": "moeda", "num": True},
        {"campo": "pre_auditoria", "rotulo": "Pré-auditoria", "formato": "moeda", "num": True},
        {"campo": "desconto_informativo", "rotulo": "Desconto", "formato": "moeda", "num": True},
        {"campo": "faturamento_grupo", "rotulo": "Faturamento", "formato": "moeda", "num": True, "sub": "situacao"},
        {"campo": "fatura_operadora", "rotulo": "Fatura operadora", "formato": "moeda", "num": True},
        {"campo": "glosa", "rotulo": "Glosa", "formato": "moeda", "num": True, "sub": "glosa_nota"},
        {"campo": "recuperado", "rotulo": "Recuperado (planilha)", "formato": "moeda", "num": True},
        {"campo": "perda", "rotulo": "Perda (planilha)", "formato": "moeda", "num": True, "sub": "status_glosa"},
        # Só no CSV
        {"campo": "protocolo", "rotulo": "Protocolo", "so_csv": True},
        {"campo": "nf_origem", "rotulo": "Origem da nota fiscal", "so_csv": True},
        {"campo": "situacao", "rotulo": "Situação da conta", "so_csv": True},
        {"campo": "unidade", "rotulo": "Unidade", "so_csv": True},
        {"campo": "pagador", "rotulo": "Pagador", "so_csv": True},
        {"campo": "tipo_nome", "rotulo": "Tipo de atendimento", "so_csv": True},
        {"campo": "id_admissao", "rotulo": "IdAdm", "so_csv": True},
        {"campo": "situacao_orcamento", "rotulo": "Situação do orçamento", "so_csv": True},
        {"campo": "orcamento_inicio", "rotulo": "Início do orçamento", "formato": "data", "so_csv": True},
        {"campo": "orcamento_fim", "rotulo": "Fim do orçamento", "formato": "data", "so_csv": True},
        {"campo": "orcamentos_na_conta", "rotulo": "Orçamentos do paciente na conta", "so_csv": True},
        {"campo": "itens", "rotulo": "Itens", "so_csv": True},
        {"campo": "dif_orcado", "rotulo": "Faturamento − orçado", "so_csv": True},
        {"campo": "itens_pre_auditados", "rotulo": "Itens pré-auditados", "so_csv": True},
        {"campo": "particular", "rotulo": "Particular", "so_csv": True},
        {"campo": "tributos_erp", "rotulo": "Tributos (ERP)", "so_csv": True},
        {"campo": "glosa_iw", "rotulo": "Glosa IW (ERP)", "so_csv": True},
        {"campo": "faturado_planilha", "rotulo": "Faturado na planilha", "so_csv": True},
        {"campo": "motivos", "rotulo": "Motivos de glosa", "so_csv": True},
        {"campo": "status_glosa", "rotulo": "Status da glosa (planilha)", "so_csv": True},
        {"campo": "origem_glosa", "rotulo": "Origem da glosa (xml/planilha)", "so_csv": True},
        {"campo": "situacao_cruzamento", "rotulo": "Cruzamento planilha × ERP", "so_csv": True},
    ],
    "carregar": carregar,
    "resumo": resumo,
}
