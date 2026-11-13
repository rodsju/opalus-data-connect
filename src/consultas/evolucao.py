"""Consultas › Evolução clínica: pendências médicas de registro por regra e tendência por IA.

Uma linha por admissão ativa na competência (sql_oracle 'evolucao_pacientes').
As pendências são regras sobre o Oracle, sem IA:
  1. nenhuma evolução médica no mês (admissão com 2+ dias no período);
  2. intercorrência sem evolução médica do dia dela até 48 h depois;
  3. prescrição médica sem evolução médica de D-1 a D+1.
"Médica" = especialidade com médic/fisiatr no nome (sql_oracle.EVOLUCAO_MEDICA).

O detalhe lê os formulários das evoluções (todas as especialidades) e mostra o que
mudou de uma para outra (reports/evolucao_campos); a tendência (melhorando,
estável, piorando) é da IA, sob demanda (reports/evolucao_ia), e aparece na lista
depois de analisada. Paciente só pelo código; conteúdo das evoluções atrás do
mesmo portão do nome (privacidade.pode_ver_nome).
"""

import concurrent.futures
import datetime

from .. import catalogo, ia, layout, provedores
from ..conciliacao import privacidade
from ..reports import comum, evolucao_campos, evolucao_ia, fonte, sql_oracle
from . import lista

MIN_DIAS = 2
LOTE = 900
TIPOS = [(str(k), v) for k, v in sql_oracle.TIPOS_ATENDIMENTO.items()]
PENDENCIAS = [("com", "Com pendência"), ("sem", "Sem pendência"), ("sem_medica", "Sem evolução médica no mês"),
              ("intercorrencia", "Intercorrência sem evolução"), ("prescricao", "Prescrição sem evolução")]
TENDENCIAS = [(k, v) for k, v in evolucao_ia.ROTULOS_TENDENCIA.items()] + [("nao_analisado", "Não analisado")]


def _unidades(_f):
    try:
        return [(u["unidade_negocio"], u["unidade_negocio"]) for u in fonte.rodar("unidades_canonicas", {})
                if u.get("unidade_negocio")]
    except comum.ConsultaFalhou:
        return []


def pendencias(l):
    """Linha com as contagens -> rótulos das pendências por regra (lista vazia = em dia)."""
    saida = []
    if not l.get("evolucoes_medicas") and comum.num(l.get("dias_no_periodo")) >= MIN_DIAS:
        saida.append("Sem evolução médica no mês")
    if l.get("interc_sem_evolucao"):
        n = int(l["interc_sem_evolucao"])
        saida.append(f"{n} intercorrência{'s' if n > 1 else ''} sem evolução médica em 48 h")
    if l.get("presc_sem_evolucao"):
        n = int(l["presc_sem_evolucao"])
        saida.append(f"{n} prescriç{'ões' if n > 1 else 'ão'} médica{'s' if n > 1 else ''} sem evolução médica")
    return saida


def _passa(l, f):
    p = f.get("pendencia")
    if p == "com" and not l["pendencias"] or p == "sem" and l["pendencias"]:
        return False
    if p == "sem_medica" and not (not l["evolucoes_medicas"] and comum.num(l["dias_no_periodo"]) >= MIN_DIAS):
        return False
    if p == "intercorrencia" and not l["interc_sem_evolucao"] or p == "prescricao" and not l["presc_sem_evolucao"]:
        return False
    t = f.get("tendencia")
    if t == "nao_analisado" and l["tendencia_chave"] or t and t != "nao_analisado" and l["tendencia_chave"] != t:
        return False
    busca = (f.get("busca") or "").strip().upper()
    return not busca or busca in (str(l["id_admissao"]), str(l.get("id_paciente")), (l.get("paciente_codigo") or ""))


def _tendencias(ids, mes):
    try:
        return evolucao_ia.tendencias(ids, mes)
    except catalogo.ConsultaFalhou:
        return {}


def montar_linhas(linhas, mes, tendencias):
    """Linhas do Oracle -> linhas da lista (pendências, tendência, link). Pura."""
    saida = []
    for l in linhas:
        pend = pendencias(l)
        ia_ = tendencias.get(l["id_admissao"]) or {}
        chave = ia_.get("tendencia")
        saida.append({**l, "mes": mes, "pendencias": pend, "pendencias_texto": " · ".join(pend) or None,
                      "situacao": "Com pendência" if pend else "Em dia",
                      "tipo_nome": sql_oracle.TIPOS_ATENDIMENTO.get(l.get("tipo"), "Outro"),
                      "tendencia_chave": chave, "tendencia": evolucao_ia.ROTULOS_TENDENCIA.get(chave),
                      "conclusao": ia_.get("conclusao"), "conclusao_chave": ia_.get("conclusao_chave"),
                      "detalhe": f"/consultas/evolucao/{l['id_admissao']}?mes={mes}"})
    return saida


def carregar(f):
    mes = f.get("mes") or comum.mes_padrao()
    filtros = comum.Filtros(mes, f.get("unidade"), tipo=f.get("tipo"))
    linhas = fonte.rodar("evolucao_pacientes", filtros.params())
    todas = montar_linhas(linhas, mes, _tendencias({l["id_admissao"] for l in linhas}, mes))
    return [l for l in todas if _passa(l, f)]


def resumo(linhas):
    conta = lambda cond: sum(1 for l in linhas if cond(l))  # noqa: E731
    return [
        {"rotulo": "Pacientes", "valor": len(linhas), "formato": "int", "icone": "users", "tom": "blue",
         "hint": f"{sum(int(l['evolucoes']) for l in linhas)} evoluções no período"},
        {"rotulo": "Com pendência", "valor": conta(lambda l: l["pendencias"]), "formato": "int",
         "icone": "triangle-alert", "tom": "coral"},
        {"rotulo": "Sem evolução médica", "valor": conta(lambda l: "Sem evolução médica no mês" in l["pendencias"]),
         "formato": "int", "icone": "stethoscope", "tom": "amber", "hint": f"admissões com {MIN_DIAS}+ dias no mês"},
        {"rotulo": "Intercorrência sem evolução", "valor": conta(lambda l: l["interc_sem_evolucao"]), "formato": "int",
         "icone": "siren", "tom": "magenta"},
        {"rotulo": "Risco alto de internação (IA)", "valor": conta(lambda l: l["conclusao_chave"] == "alto"),
         "formato": "int", "icone": "ambulance", "tom": "coral", "hint": "home care"},
        {"rotulo": "Piorando (IA)", "valor": conta(lambda l: l["tendencia_chave"] == "piorando"), "formato": "int",
         "icone": "trending-down", "tom": "violet",
         "hint": f"{conta(lambda l: l['tendencia_chave'])} analisados"},
    ]


CONSULTA = {
    "slug": "evolucao", "titulo": "Evolução clínica", "icone": "activity",
    "descricao": "Pendências médicas de registro por paciente na competência (sem evolução médica no mês; "
                 "intercorrência sem evolução médica em 48 h; prescrição médica sem evolução de D-1 a D+1) e a "
                 "leitura da IA, sob demanda no detalhe, com uma pergunta por tipo: home care → risco de "
                 "internação; hospital de transição → desfecho provável; ambulatório → meta da reabilitação. "
                 "Apoio à coordenação; não substitui avaliação médica.",
    "filtros": [
        {"nome": "mes", "rotulo": "Competência", "tipo": "mes", "padrao": ""},
        {"nome": "unidade", "rotulo": "Unidade (provider)", "tipo": "select", "opcoes": _unidades},
        {"nome": "tipo", "rotulo": "Tipo de atendimento", "tipo": "select", "opcoes": TIPOS},
        {"nome": "pendencia", "rotulo": "Pendência", "tipo": "select", "opcoes": PENDENCIAS},
        {"nome": "tendencia", "rotulo": "Tendência (IA)", "tipo": "select", "opcoes": TENDENCIAS},
        {"nome": "busca", "rotulo": "IdAdm, ID ou código do paciente", "tipo": "texto"},
    ],
    "colunas": [
        {"campo": "id_admissao", "rotulo": "IdAdm", "formato": "mono", "link": "{detalhe}"},
        {"campo": "paciente_codigo", "rotulo": "Código", "formato": "codigo_paciente"},
        {"campo": "paciente_codigo", "rotulo": "Nome", "formato": "nome_paciente", "so_tela": True},
        {"campo": "unidade", "rotulo": "Unidade", "sub": "tipo_nome"},
        {"campo": "operadora", "rotulo": "Operadora"},
        {"campo": "evolucoes", "rotulo": "Evoluções", "formato": "int", "num": True},
        {"campo": "evolucoes_medicas", "rotulo": "Médicas", "formato": "int", "num": True, "sub": "ultima_medica"},
        {"campo": "intercorrencias", "rotulo": "Intercorr.", "formato": "int", "num": True},
        {"campo": "prescricoes", "rotulo": "Prescr. médicas", "formato": "int", "num": True},
        {"campo": "situacao", "rotulo": "Pendências", "formato": "badge", "sub": "pendencias_texto"},
        {"campo": "tendencia", "rotulo": "Tendência (IA)", "formato": "badge", "sub": "conclusao"},
        # Só no CSV
        {"campo": "mes", "rotulo": "Competência", "so_csv": True},
        {"campo": "id_paciente", "rotulo": "ID paciente (Oracle)", "so_csv": True},
        {"campo": "tipo_nome", "rotulo": "Tipo de atendimento", "so_csv": True},
        {"campo": "entrada", "rotulo": "Entrada", "formato": "data", "so_csv": True},
        {"campo": "saida", "rotulo": "Saída", "formato": "data", "so_csv": True},
        {"campo": "dias_no_periodo", "rotulo": "Dias no período", "so_csv": True},
        {"campo": "ultima_medica", "rotulo": "Última evolução médica", "formato": "data", "so_csv": True},
        {"campo": "interc_sem_evolucao", "rotulo": "Intercorrências sem evolução", "so_csv": True},
        {"campo": "presc_sem_evolucao", "rotulo": "Prescrições sem evolução", "so_csv": True},
        {"campo": "pendencias_texto", "rotulo": "Pendências (detalhe)", "so_csv": True},
        {"campo": "conclusao", "rotulo": "Conclusão da IA (por tipo)", "so_csv": True},
    ],
    "carregar": carregar,
    "resumo": resumo,
}


# --------------------------------------------------------------------------
# Detalhe de uma admissão na competência
# --------------------------------------------------------------------------


def _formularios(evolucoes):
    """{id_evolucao: campos} lendo cada tabela TD* uma vez. Devolve (campos, tabelas que falharam)."""
    tabelas = {}
    for e in evolucoes:
        if e.get("tabela"):
            tabelas.setdefault(e["tabela"].upper(), []).append(e["id_evolucao"])
    if not tabelas:
        return {}, []
    rotulos = {}
    for r in fonte.rodar("evolucao_rotulos", {"TABELAS": sorted(tabelas)}):
        rotulos.setdefault(r["tabela"], {})[r["campo"]] = r
    campos, falhas = {}, []
    for tabela, ids in tabelas.items():
        try:
            linhas = [l for i in range(0, len(ids), LOTE) for l in fonte.formulario(tabela, ids[i:i + LOTE])]
        except (comum.ConsultaFalhou, ValueError):
            falhas.append(tabela)
            continue
        # Nenhuma linha para nenhuma evolução: a tabela do template não existe/não é visível (ex.: a ficha do
        # ambulatório aponta para TDWD_AMBULATORIO, que não existe no schema) -- é falta de dado, não "sem campos".
        if not linhas:
            falhas.append(tabela)
        for linha in linhas:
            campos[linha.get("idevolution")] = evolucao_campos.campos(linha, rotulos.get(tabela, {}))
    return campos, falhas


def historico(linhas):
    """Admissões do paciente -> com nome do tipo e do desfecho (sql_oracle.DESFECHOS). Pura."""
    return [{**h, "tipo_nome": sql_oracle.TIPOS_ATENDIMENTO.get(h.get("tipo"), "Outro"),
             "desfecho_nome": ("em atendimento" if not h.get("saida") else
                               sql_oracle.DESFECHOS.get(h.get("desfecho"), f"outro (código {h.get('desfecho')})"))}
            for h in linhas]


def resumo_sessoes(sessoes, agora=None):
    """Agenda do ambulatório -> agendadas, compareceu, faltas, canceladas, realizadas sem evolução. Pura."""
    agora = agora or datetime.datetime.now()
    validas = [x for x in sessoes if not x["cancelada"]]
    return {"agendadas": len(validas), "compareceu": sum(1 for x in validas if x["compareceu"]),
            "faltas": sum(1 for x in validas if not x["compareceu"] and x["data"] and x["data"] < agora),
            "canceladas": len(sessoes) - len(validas),
            "realizadas_sem_evolucao": sum(1 for x in validas if x["compareceu"] and not x["com_evolucao"])}


def por_tipo(adm, hist, sessoes, fim):
    """O que só a pergunta do tipo de atendimento usa (evolucao_ia.FOCOS). Pura."""
    if adm.get("tipo") == 1:  # home care: internações recentes
        limite = fim - datetime.timedelta(days=90)
        return {"internacoes_90d": sum(1 for h in hist if h.get("desfecho") == 1 and h.get("saida")
                                       and h["saida"] >= limite)}
    if adm.get("tipo") == 0 and adm.get("entrada"):  # transição: dias internado até o fim do período
        return {"dias_internado": (min(adm.get("saida") or fim, fim) - adm["entrada"]).days}
    if adm.get("tipo") == 3:
        return {"sessoes": resumo_sessoes(sessoes)}
    return {}


def montar_contexto(id_admissao, mes):
    """Tudo o que o detalhe e a IA precisam. None se a admissão não existe."""
    inicio, fim = comum.periodo(mes)
    p = {"ID": id_admissao, "DT_INI": inicio, "DT_FIM": fim}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futuros = {n: pool.submit(fonte.rodar, n, p) for n in
                   ("evolucao_admissao", "evolucao_lista", "evolucao_intercorrencias", "evolucao_prescricoes")}
        dados = {n: f.result() for n, f in futuros.items()}
    if not dados["evolucao_admissao"]:
        return None
    adm = dados["evolucao_admissao"][0]
    adm = {**adm, "tipo_nome": sql_oracle.TIPOS_ATENDIMENTO.get(adm.get("tipo"), "Outro")}
    evolucoes = dados["evolucao_lista"]
    campos, falhas = _formularios(evolucoes)
    for e in evolucoes:
        e["campos"] = campos.get(e["id_evolucao"], {})
        e["formulario_chave"] = e.get("id_template")
    evolucao_campos.com_mudancas(evolucoes)
    hist = historico(fonte.rodar("evolucao_historico", {**p, "ID": adm["id_paciente"]})) if adm.get("id_paciente") else []
    sessoes = fonte.rodar("evolucao_sessoes", p) if adm.get("tipo") == 3 else []
    entrada, saida = adm.get("entrada"), adm.get("saida")
    ini_dt, fim_dt = datetime.datetime.combine(inicio, datetime.time()), datetime.datetime.combine(fim, datetime.time())
    dias = ((min(saida or fim_dt, fim_dt) - max(entrada or ini_dt, ini_dt)).total_seconds() / 86400
            if entrada else None)
    contagens = {"evolucoes_medicas": sum(1 for e in evolucoes if e["medica"]), "dias_no_periodo": dias,
                 "interc_sem_evolucao": sum(1 for i in dados["evolucao_intercorrencias"] if i["sem_evolucao"]),
                 "presc_sem_evolucao": sum(1 for x in dados["evolucao_prescricoes"] if x["sem_evolucao"])}
    return {
        "admissao": adm, "mes": mes, "dias_no_periodo": round(dias, 1) if dias is not None else None,
        "evolucoes": evolucoes, "intercorrencias": dados["evolucao_intercorrencias"],
        "prescricoes": dados["evolucao_prescricoes"], "pendencias": pendencias(contagens),
        "formularios_indisponiveis": falhas,
        "por_especialidade": sorted(
            {e["especialidade"]: sum(1 for x in evolucoes if x["especialidade"] == e["especialidade"])
             for e in evolucoes}.items(), key=lambda kv: -kv[1]),
        "copias": sum(1 for e in evolucoes if not e["base"] and not e["mudou"]),
        "historico": hist, "sessoes": sessoes,
        "por_tipo": por_tipo(adm, hist, sessoes, fim_dt),
        "foco": evolucao_ia.foco(adm.get("tipo")),
    }


def _sem_conteudo(ctx):
    """Sem permissão: fica a linha do tempo, sai o conteúdo dos formulários."""
    for e in ctx["evolucoes"]:
        e["campos"], e["mudou"] = {}, {}
    return ctx


def gerar_detalhe(usuario, id_admissao, mes, aviso=None, erro=None):
    mes = mes or comum.mes_padrao()
    try:
        ctx = montar_contexto(id_admissao, mes)
    except comum.ConsultaFalhou as falha:
        ctx, erro = None, {"motivo": falha.motivo, "detalhe": falha.dica}
    if ctx is None and not erro:
        return None, 404
    pode_ver = privacidade.pode_ver_nome(usuario)
    if ctx and not pode_ver:
        ctx = _sem_conteudo(ctx)
    analise = None
    if ctx:
        try:
            analise = evolucao_ia.ultima(id_admissao, mes)
        except catalogo.ConsultaFalhou:
            analise = None
    try:
        motores = evolucao_ia.motores()
    except catalogo.ConsultaFalhou:
        motores = []
    html = layout.render(
        "consultas/evolucao_detalhe.html", f"Evolução · admissão {id_admissao}", usuario, "/consultas/evolucao",
        ctx=ctx, id_admissao=id_admissao, mes=mes, analise=analise, motores=motores, pode_ver=pode_ver,
        aviso=aviso, erro=erro, rotulos_tendencia=evolucao_ia.ROTULOS_TENDENCIA, consultas=lista.CONSULTAS_MENU)
    return html, 200


def _nome(id_paciente):
    """Nome só para tirar do texto antes da IA; nunca vai para a tela nem para o log."""
    try:
        linhas = fonte.rodar("paciente_nome", {"ID": id_paciente}) if id_paciente else []
    except comum.ConsultaFalhou:
        return None
    return linhas[0]["nome"] if linhas else None


def analisar(id_admissao, mes, usuario, forcar=False, par=None):
    """(aviso, erro) da análise por IA da admissão na competência."""
    if not privacidade.pode_ver_nome(usuario):
        return None, {"motivo": "sem permissão para analisar dados clínicos", "detalhe": ""}
    try:
        ctx = montar_contexto(id_admissao, mes)
        if ctx is None:
            return None, {"motivo": "admissão não encontrada", "detalhe": str(id_admissao)}
        if not ctx["evolucoes"]:
            return None, {"motivo": "sem evoluções no período", "detalhe": "Nada para a IA ler nesta competência."}
        registro, reaproveitada = evolucao_ia.analisar(ctx, _nome(ctx["admissao"]["id_paciente"]),
                                                       autor=(usuario or {}).get("email"), forcar=forcar,
                                                       par=par or None)
    except (comum.ConsultaFalhou, catalogo.ConsultaFalhou) as falha:
        return None, {"motivo": getattr(falha, "motivo", str(falha)), "detalhe": getattr(falha, "dica", "")}
    except provedores.ConfiguracaoInvalida as falha:
        return None, {"motivo": str(falha), "detalhe": "Cadastre um provedor em Setup › AI Providers."}
    except ia.GeracaoFalhou as falha:
        return None, {"motivo": falha.motivo, "detalhe": getattr(falha, "detalhe", "")}
    tendencia = evolucao_ia.ROTULOS_TENDENCIA.get((registro["resultado"] or {}).get("tendencia"), "?")
    if reaproveitada:
        return f"Nada mudou desde a última análise (tendência: {tendencia}): reaproveitada sem nova chamada à IA.", None
    return f"Análise concluída por {registro['modelo']}: tendência {tendencia}.", None
