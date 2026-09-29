"""As consultas do app (ferramentas linha a linha) e o menu delas."""

import datetime

from ..conciliacao import cruzamento, regras
from ..reports import comum, fonte
from . import lista

TIPOS = [("0", "Hospital de transição"), ("1", "Home care"), ("3", "Ambulatorial")]
FAIXAS_PRAZO = ["vencido", "até 7 dias", "8 a 15 dias", "16 a 30 dias", "mais de 30 dias", "sem prazo"]


def _pg_lista(nome, campo):
    def opcoes(_filtros):
        try:
            return [(l[campo], l[campo]) for l in fonte.rodar(nome, {}) if l.get(campo)]
        except comum.ConsultaFalhou:
            return []
    return opcoes


def _motivos(_filtros):
    try:
        return [(l["motivo"], f"{l['motivo']} · {(l['descricao'] or '').capitalize()[:50]}")
                for l in fonte.rodar("gm_motivos", {})]
    except comum.ConsultaFalhou:
        return []


def _periodo(filtros):
    mes = filtros.get("mes")
    return comum.periodo(mes) if mes else (None, None)


# --------------------------------------------------------------------------
# Glosas linha a linha (planilha + cruzamento com o ERP)
# --------------------------------------------------------------------------


def rotulo_origem(origem):
    """'xml' | 'planilha' | 'planilha/xml' -> '(xml)' / '(planilha)' / '(xml/planilha)'."""
    partes = sorted(set((origem or "planilha").split("/")), key=lambda o: o != "xml")
    return f"({'/'.join(partes)})"


def com_origem(l):
    """Rótulos de origem da glosa numa linha de glosa_efetiva."""
    xml = l.get("origem_glosa") == "xml"
    nota = (l.get("motivo_descricao") or "").capitalize()
    if xml and l.get("motivo_planilha") and l.get("motivo_planilha") != l.get("motivo"):
        nota = f"{nota} · planilha dizia {l['motivo_planilha']}".strip(" ·")
    return {**l, "origem_rotulo": rotulo_origem(l.get("origem_glosa")), "motivo_nota": nota}


def carregar_glosas(f):
    inicio, fim = _periodo(f)
    return [com_origem(l) for l in _glosas_efetivas(inicio, fim, f)]


def _glosas_efetivas(inicio, fim, f):
    return fonte.rodar("cs_glosas", {
        "DT_INI": inicio, "DT_FIM": fim, "UNIDADE": f.get("unidade") or None, "CONVENIO": f.get("convenio") or None,
        "MOTIVO": f.get("motivo") or None, "TIPO": int(f["tipo"]) if f.get("tipo") else None,
        "STATUS": f.get("status") or None, "SITUACAO": f.get("situacao") or None, "PRAZO": f.get("prazo") or None,
        "ORIGEM": f.get("origem") or None,
    })


def _divisao_origem(linhas):
    from .. import layout

    xml = sum(comum.num(l["glosa"]) for l in linhas if l.get("origem_glosa") == "xml")
    total = sum(comum.num(l["glosa"]) for l in linhas)
    return f"{layout.fmt_moeda_curta(xml)} (xml) · {layout.fmt_moeda_curta(total - xml)} (planilha)"


def resumo_glosas(linhas):
    return [
        {"rotulo": "Linhas", "valor": len(linhas), "formato": "int", "icone": "rows-3", "tom": "blue"},
        {"rotulo": "Glosa", "valor": sum(comum.num(l["glosa"]) for l in linhas), "formato": "moeda_curta",
         "icone": "shield-x", "tom": "coral", "hint": _divisao_origem(linhas)},
        {"rotulo": "Recuperado", "valor": sum(comum.num(l["recuperado"]) for l in linhas), "formato": "moeda_curta",
         "icone": "rotate-ccw", "tom": "teal"},
        {"rotulo": "Perda", "valor": sum(comum.num(l["perda"]) for l in linhas), "formato": "moeda_curta",
         "icone": "trending-down", "tom": "magenta"},
    ]


GLOSAS = {
    "slug": "glosas", "titulo": "Glosas linha a linha", "icone": "list-x",
    "descricao": "Cada glosa com o motivo TISS, o desfecho, o prazo de recurso e o casamento com a conta do ERP. "
                 "Valor e motivo vêm do XML da operadora quando houver (xml); recurso, recuperado e perda, da "
                 "planilha. Filtre, ordene e exporte.",
    "filtros": [
        {"nome": "mes", "rotulo": "Competência", "tipo": "mes"},
        {"nome": "unidade", "rotulo": "Empresa · filial", "tipo": "select", "opcoes": _pg_lista("gp_unidades", "unidade")},
        {"nome": "convenio", "rotulo": "Convênio", "tipo": "select", "opcoes": _pg_lista("gp_convenios", "convenio")},
        {"nome": "motivo", "rotulo": "Motivo (TISS)", "tipo": "select", "opcoes": _motivos},
        {"nome": "status", "rotulo": "Status da glosa", "tipo": "select", "opcoes": [(s, s) for s in regras.STATUS_GLOSA]},
        {"nome": "prazo", "rotulo": "Prazo de recurso", "tipo": "select", "opcoes": [(p, p) for p in FAIXAS_PRAZO]},
        {"nome": "situacao", "rotulo": "Cruzamento com o ERP", "tipo": "select",
         "opcoes": [(s, s.capitalize()) for s in cruzamento.SITUACOES]},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select", "opcoes": TIPOS},
        {"nome": "origem", "rotulo": "Origem da glosa", "tipo": "select",
         "opcoes": [("xml", "XML da operadora"), ("planilha", "Planilha")]},
    ],
    "colunas": [
        {"campo": "competencia", "rotulo": "Comp.", "formato": "data"},
        {"campo": "convenio", "rotulo": "Convênio", "sub": "unidade"},
        {"campo": "id_paciente", "rotulo": "ID paciente (Oracle)", "formato": "mono"},
        {"campo": "paciente_codigo", "rotulo": "Código", "formato": "codigo_paciente"},
        {"campo": "paciente_codigo", "rotulo": "Nome", "formato": "nome_paciente", "so_tela": True},
        {"campo": "protocolo", "rotulo": "Protocolo", "formato": "mono"},
        {"campo": "motivo", "rotulo": "Motivo", "formato": "mono", "sub": "motivo_nota"},
        {"campo": "classificacao", "rotulo": "Classificação"},
        {"campo": "status_glosa", "rotulo": "Status (planilha)", "formato": "badge"},
        {"campo": "glosa", "rotulo": "Glosa", "formato": "moeda", "num": True, "sub": "origem_rotulo"},
        {"campo": "valor_recursado", "rotulo": "Recorrido (planilha)", "formato": "moeda", "num": True},
        {"campo": "recuperado", "rotulo": "Recuperado (planilha)", "formato": "moeda", "num": True},
        {"campo": "perda", "rotulo": "Perda (planilha)", "formato": "moeda", "num": True},
        {"campo": "prazo_recurso", "rotulo": "Prazo recurso", "formato": "data", "sub": "dias_recurso"},
        {"campo": "situacao", "rotulo": "Cruzamento", "sub": "regra"},
        {"campo": "valor_faturado", "rotulo": "Faturado planilha", "formato": "moeda", "num": True},
        {"campo": "faturado_erp", "rotulo": "Faturado ERP", "formato": "moeda", "num": True},
        {"campo": "id_conta", "rotulo": "Conta ERP", "formato": "mono"},
        {"campo": "tipo_atendimento", "rotulo": "Tipo"},
        {"campo": "unidade", "rotulo": "Empresa · filial", "so_csv": True},
        {"campo": "motivo_descricao", "rotulo": "Descrição do motivo", "so_csv": True},
        {"campo": "origem_glosa", "rotulo": "Origem da glosa (xml/planilha)", "so_csv": True},
        {"campo": "motivos_xml", "rotulo": "Motivos no XML", "so_csv": True},
        {"campo": "motivo_planilha", "rotulo": "Motivo na planilha", "so_csv": True},
        {"campo": "glosa_planilha", "rotulo": "Glosa na planilha", "so_csv": True},
    ],
    "carregar": carregar_glosas,
    "resumo": resumo_glosas,
}


# --------------------------------------------------------------------------
# Opções compartilhadas
# --------------------------------------------------------------------------


def _unidades_faturam(_f):
    try:
        return [(l["unidade"].strip(), l["unidade"].strip()) for l in fonte.rodar("unidades_faturam", {})
                if l.get("unidade")]
    except comum.ConsultaFalhou:
        return []


# --------------------------------------------------------------------------
# Pacientes em atendimento (ocupação, Oracle)
# --------------------------------------------------------------------------

NOMES_TIPO = dict(TIPOS)


def carregar_pacientes(f):
    filtros = comum.Filtros(comum.mes_padrao(), f.get("unidade"), tipo=f.get("tipo"))
    linhas = fonte.rodar("pacientes_em_atendimento", filtros.params(com_periodo=False))
    setor, busca = (f.get("setor") or "").strip().upper(), (f.get("busca") or "").strip().upper()
    saida = []
    for l in linhas:
        if setor and setor not in (l.get("setor") or "").upper():
            continue
        if busca and busca not in (str(l["id_admissao"]), str(l.get("id_paciente")), (l.get("paciente_codigo") or "").upper()):
            continue
        saida.append({**l, "tipo_nome": NOMES_TIPO.get(str(l["tipo"]), str(l["tipo"]))})
    return saida


def _unidades_provider(_f):
    try:
        return [(u["unidade_negocio"], u["unidade_negocio"]) for u in fonte.rodar("unidades_canonicas", {})
                if u.get("unidade_negocio")]
    except comum.ConsultaFalhou:
        return []


PACIENTES = {
    "slug": "pacientes", "titulo": "Pacientes em atendimento", "icone": "bed",
    "descricao": "Quem está ocupando uma vaga agora: admissões com status em atendimento, por unidade, tipo de "
                 "atendimento e setor (local de acomodação). Paciente só pelo código.",
    "filtros": [
        {"nome": "unidade", "rotulo": "Unidade (provider)", "tipo": "select", "opcoes": _unidades_provider},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select", "opcoes": TIPOS},
        {"nome": "setor", "rotulo": "Setor / local", "tipo": "texto"},
        {"nome": "busca", "rotulo": "IdAdm, ID ou código do paciente", "tipo": "texto"},
    ],
    "colunas": [
        {"campo": "id_admissao", "rotulo": "IdAdm", "formato": "mono"},
        {"campo": "id_paciente", "rotulo": "ID paciente (Oracle)", "formato": "mono"},
        {"campo": "paciente_codigo", "rotulo": "Código", "formato": "codigo_paciente"},
        {"campo": "paciente_codigo", "rotulo": "Nome", "formato": "nome_paciente", "so_tela": True},
        {"campo": "unidade", "rotulo": "Unidade", "sub": "tipo_nome"},
        {"campo": "setor", "rotulo": "Local de acomodação"},
        {"campo": "entrada", "rotulo": "Entrada", "formato": "data"},
        {"campo": "dias", "rotulo": "Dias", "formato": "int", "num": True},
        {"campo": "operadora", "rotulo": "Operadora"},
        {"campo": "tipo_nome", "rotulo": "Tipo de atendimento", "so_csv": True},
    ],
    "carregar": carregar_pacientes,
    "resumo": lambda linhas: [
        {"rotulo": "Em atendimento", "valor": len(linhas), "formato": "int", "icone": "user-check", "tom": "teal"},
        {"rotulo": "Transição", "valor": sum(1 for l in linhas if l["tipo"] == 0), "formato": "int", "icone": "bed",
         "tom": "blue"},
        {"rotulo": "Home care", "valor": sum(1 for l in linhas if l["tipo"] == 1), "formato": "int", "icone": "house",
         "tom": "magenta"},
        {"rotulo": "Permanência média", "valor": (sum(comum.num(l["dias"]) for l in linhas) / len(linhas)) if linhas else None,
         "formato": "int", "icone": "calendar-clock", "tom": "violet", "hint": "dias"},
    ],
}


# --------------------------------------------------------------------------
# Pré-auditoria (glosa interna antes do envio, Oracle)
# --------------------------------------------------------------------------


def carregar_pre_auditoria(f):
    from ..reports import bloco_pre_auditoria

    if f.get("mes"):
        inicio, fim = comum.periodo(f["mes"])
    else:  # sem competência: os últimos 12 meses
        fim = (datetime.date.today().replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
        inicio = fim
        for _ in range(12):
            inicio = (inicio - datetime.timedelta(days=1)).replace(day=1)
    linhas = fonte.rodar("pre_auditoria_itens", {
        "DT_INI": inicio, "DT_FIM": fim, "UNIDADE": f.get("unidade") or None,
        "TIPO": int(f["tipo"]) if f.get("tipo") else None})
    textos = bloco_pre_auditoria.descricoes()
    motivo = (f.get("motivo") or "").strip()
    busca = (f.get("busca") or "").strip().upper()
    saida = []
    for l in linhas:
        if motivo and l.get("motivo") != motivo:
            continue
        glosou = comum.num(l.get("glosa_depois")) != 0
        if f.get("glosa") == "sim" and not glosou or f.get("glosa") == "nao" and glosou:
            continue
        if busca and busca not in (str(l["id_conta"]), str(l.get("id_paciente")), (l.get("paciente_codigo") or "")):
            continue
        descricao, origem = textos.get(l.get("motivo"), (None, None))
        competencia = l.get("competencia")
        saida.append({**l, "competencia": competencia.date() if hasattr(competencia, "date") else competencia,
                      "id_item": l["id_item"] if l.get("tem_comentario") else None,
                      "motivo_descricao": descricao, "motivo_origem": origem,
                      "tipo_nome": NOMES_TIPO.get(str(l.get("tipo")), ""),
                      "glosou": "sim" if glosou else "não"})
    return saida


PRE_AUDITORIA = {
    "slug": "pre-auditoria", "titulo": "Pré-auditoria", "icone": "scan-search",
    "descricao": "Cada item que a auditoria interna cortou antes de a conta ir para a operadora, com o motivo, o "
                 "comentário do auditor e se a operadora ainda glosou depois. Sem competência: últimos 12 meses.",
    "filtros": [
        {"nome": "mes", "rotulo": "Competência", "tipo": "mes", "padrao": ""},
        {"nome": "unidade", "rotulo": "Unidade", "tipo": "select", "opcoes": _unidades_faturam},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select", "opcoes": TIPOS},
        {"nome": "motivo", "rotulo": "Motivo (código)", "tipo": "texto"},
        {"nome": "glosa", "rotulo": "Glosado depois", "tipo": "select", "opcoes": [("sim", "Sim"), ("nao", "Não")]},
        {"nome": "busca", "rotulo": "Conta, ID ou código do paciente", "tipo": "texto"},
    ],
    "colunas": [
        {"campo": "competencia", "rotulo": "Comp.", "formato": "data"},
        {"campo": "id_conta", "rotulo": "Conta", "formato": "mono"},
        {"campo": "operadora", "rotulo": "Operadora", "sub": "unidade"},
        {"campo": "id_paciente", "rotulo": "ID paciente (Oracle)", "formato": "mono"},
        {"campo": "paciente_codigo", "rotulo": "Código", "formato": "codigo_paciente"},
        {"campo": "paciente_codigo", "rotulo": "Nome", "formato": "nome_paciente", "so_tela": True},
        {"campo": "recurso", "rotulo": "Recurso", "formato": "texto_longo"},
        {"campo": "quantidade", "rotulo": "Qtd", "formato": "int", "num": True},
        {"campo": "qtd_pre", "rotulo": "Qtd cortada", "formato": "int", "num": True},
        {"campo": "pre_auditoria", "rotulo": "Cortado", "formato": "moeda", "num": True},
        {"campo": "motivo", "rotulo": "Motivo", "formato": "mono", "sub": "motivo_descricao"},
        {"campo": "id_item", "rotulo": "Comentário do auditor", "formato": "comentario_oculto", "so_tela": True},
        {"campo": "glosa_depois", "rotulo": "Glosa depois", "formato": "moeda", "num": True},
        {"campo": "unidade", "rotulo": "Unidade", "so_csv": True},
        {"campo": "tipo_nome", "rotulo": "Tipo de atendimento", "so_csv": True},
        {"campo": "id_admissao", "rotulo": "IdAdm", "so_csv": True},
        {"campo": "preco", "rotulo": "Preço unitário", "so_csv": True},
        {"campo": "valor_informado", "rotulo": "Valor informado (PREAUDITBILLVALUE)", "so_csv": True},
        {"campo": "motivo_descricao", "rotulo": "Descrição do motivo", "so_csv": True},
        {"campo": "motivo_origem", "rotulo": "Origem do motivo", "so_csv": True},
    ],
    "carregar": carregar_pre_auditoria,
    "resumo": lambda linhas: [
        {"rotulo": "Itens", "valor": len(linhas), "formato": "int", "icone": "list-checks", "tom": "blue"},
        {"rotulo": "Cortado antes do envio", "valor": sum(comum.num(l["pre_auditoria"]) for l in linhas),
         "formato": "moeda_curta", "icone": "scan-search", "tom": "violet"},
        {"rotulo": "Glosados depois", "valor": sum(1 for l in linhas if l["glosou"] == "sim"), "formato": "int",
         "icone": "shield-x", "tom": "coral",
         "hint": "itens que a operadora ainda glosou"},
    ],
}


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------

from . import conta_paciente, faturas, orcamentos  # noqa: E402

CONSULTAS = {c["slug"]: c for c in (faturas.CONSULTA, conta_paciente.CONSULTA, GLOSAS, PRE_AUDITORIA,
                                    orcamentos.CONSULTA, PACIENTES)}
lista.CONSULTAS_MENU[:] = [{"slug": c["slug"], "titulo": c["titulo"], "icone": c["icone"],
                            "href": f"/consultas/{c['slug']}", "ativo": False} for c in CONSULTAS.values()]
