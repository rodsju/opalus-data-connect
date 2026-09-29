"""Páginas de relatório: cada uma é uma lista de blocos sobre o mesmo recorte."""

import concurrent.futures
import logging
import time

from .. import layout
from . import (
    bloco_auditoria,
    bloco_oc_evolucao,
    bloco_oc_hc,
    bloco_oc_leitos,
    bloco_oc_resumo,
    bloco_oc_unidades,
    bloco_cascata,
    bloco_contas_abertas,
    bloco_contas_status,
    bloco_faturamento_operadora,
    bloco_gap_orcamento,
    bloco_glosa_operadora,
    bloco_glosa_unidade,
    bloco_gm_convenio,
    bloco_gm_desfecho,
    bloco_gm_evolucao,
    bloco_gm_ranking,
    bloco_gp_cascata,
    bloco_gp_classificacao,
    bloco_gp_convenio,
    bloco_gp_evolucao,
    bloco_gp_funil,
    bloco_gp_motivo,
    bloco_gp_prazo_recurso,
    bloco_gp_resumo,
    bloco_gp_unidade,
    bloco_motivos_glosa,
    bloco_orcamentos_status,
    bloco_pre_auditoria,
    bloco_resumo,
    comum,
)

logger = logging.getLogger(__name__)

# Blocos rodando ao mesmo tempo no Oracle. Cada um abre a própria conexão.
PARALELO = 4

RELATORIOS = {
    "faturamento": {
        "titulo": "Faturamento",
        "icone": "receipt",
        "descricao": "A conta do mês em cascata (bruto → pacote → pré-auditoria → particular → fatura da operadora), "
        "a glosa interna cortada antes do envio, por situação, entidade pagadora e o que ainda está em aberto.",
        "dimensao": "homecare",
        "blocos": [bloco_resumo, bloco_cascata, bloco_pre_auditoria, bloco_contas_status,
                   bloco_faturamento_operadora, bloco_contas_abertas],
    },
    "glosa-iw": {
        "titulo": "Glosa IW",
        "icone": "shield-x",
        "descricao": "Glosa registrada no ERP (auditoria de conta do IW), por unidade, operadora e motivo.",
        "dimensao": "homecare",
        "aviso_forte": "O ERP deixou de registrar glosa em jul/2025: desde então o controle é a planilha. "
        "Use Glosa (xml/planilha) para os números atuais.",
        "aviso": "A glosa chega meses depois da competência: os meses mais recentes parecem "
        "artificialmente limpos.",
        "blocos": [bloco_glosa_unidade, bloco_glosa_operadora, bloco_motivos_glosa],
    },
    "glosa-planilha": {
        "titulo": "Glosa (xml/planilha)",
        "icone": "sheet",
        "descricao": "Glosa por convênio, motivo e prazo. Valor e motivo vêm do XML TISS da operadora quando houver "
        "(xml); o resto e o recurso, recuperação e perda, da planilha base_glosa (planilha).",
        "dimensao": "planilha",
        "fonte": "planilha",
        "periodo_opcional": True,
        "filtro_convenio": True,
        "blocos": [bloco_gp_resumo, bloco_gp_cascata, bloco_gp_evolucao, bloco_gp_funil, bloco_gp_classificacao,
                   bloco_gp_convenio, bloco_gp_prazo_recurso, bloco_gp_motivo, bloco_gp_unidade],
    },
    "glosa-motivos": {
        "titulo": "Motivos de glosa",
        "icone": "tags",
        "descricao": "Cada código de glosa (Tabela 38 do TISS): quanto pesa, onde aparece, o que voltou em recurso "
        "e o que se perdeu. Clique num código para ver todos os casos.",
        "dimensao": "planilha",
        "fonte": "planilha",
        "periodo_opcional": True,
        "filtro_convenio": True,
        "filtro_motivo": True,
        "blocos": [bloco_gm_ranking, bloco_gm_desfecho, bloco_gm_convenio, bloco_gm_evolucao],
    },
    "orcamentos": {
        "titulo": "Orçamentos",
        "icone": "clipboard-list",
        "descricao": "Autorização dos orçamentos do mês e a receita autorizada que ainda não foi faturada.",
        "dimensao": "provider",
        "aviso": "Orçamento usa a unidade de negócio canônica (GLBHEALTHPROVIDER, ex.: 'Premier Brooklin "
        "HSP'), diferente da unidade do faturamento.",
        "blocos": [bloco_orcamentos_status, bloco_gap_orcamento],
    },
    "ocupacao": {
        "titulo": "Ocupação",
        "icone": "bed",
        "descricao": "Taxa de ocupação do hospital de transição (ocupados ÷ leitos) e censo do home care, por "
        "unidade, agora e nos últimos 90 dias. Ocupado = admissão em atendimento.",
        "dimensao": "provider",
        "sem_periodo": True,
        "blocos": [bloco_oc_resumo, bloco_oc_unidades, bloco_oc_leitos, bloco_oc_hc, bloco_oc_evolucao],
    },
    "auditoria": {
        "titulo": "Auditoria de contas",
        "icone": "scale",
        "descricao": "Foto da última execução da auditoria em cada unidade: declarado × reconhecido.",
        "dimensao": "homecare",
        "sem_periodo": True,
        "filtro_tipo": False,  # TTMPAUDITBILLCTR não chega à admissão
        "blocos": [bloco_auditoria],
    },
}

# Todos os blocos, uma vez cada, na ordem em que aparecem nos relatórios.
BLOCOS = list(dict.fromkeys(b for r in RELATORIOS.values() for b in r["blocos"]))


def slug_do_bloco(modulo):
    return modulo.__name__.rsplit(".", 1)[-1].removeprefix("bloco_")


def descrever(modulo, dados, ms=None, sem_conexao=False):
    return {
        "slug": slug_do_bloco(modulo),
        "titulo": modulo.TITULO,
        "icone": modulo.ICONE,
        "partial": modulo.PARTIAL,
        "largura": modulo.LARGURA,
        "itens": modulo.ITENS,
        "dados": dados,
        "ms": ms,
        "sem_conexao": sem_conexao,
    }


def _executar(modulo, filtros):
    inicio = time.perf_counter()
    sem_conexao = False
    try:
        dados = modulo.consultar(filtros)
    except comum.ConsultaFalhou as falha:
        dados = {"erro": falha.motivo, "dica": falha.dica}
        sem_conexao = falha.sem_conexao
    except Exception as falha:  # noqa: BLE001 -- um bloco quebrado não derruba a página
        logger.exception("reports: bloco %s quebrou", modulo.__name__)
        dados = {"erro": "falha ao montar o bloco", "dica": str(falha)}
    return descrever(modulo, dados, (time.perf_counter() - inicio) * 1000, sem_conexao)


def _unidades(filtros, dimensao):
    """Opções do filtro de unidade, na dimensão que o relatório usa."""
    try:
        if dimensao == "planilha":
            return [l["unidade"] for l in filtros.rodar("gp_unidades", com_periodo=False, unidade=False)]
        if dimensao == "provider":
            linhas = filtros.rodar("unidades_canonicas", com_periodo=False, unidade=False)
            return [l["unidade_negocio"] for l in linhas if l.get("unidade_negocio")]
        linhas = filtros.rodar("unidades_faturam", com_periodo=False, unidade=False)
        return [(l["unidade"] or "").strip() for l in linhas if l.get("unidade")]
    except comum.ConsultaFalhou:
        return []


def _convenios(filtros):
    try:
        return [l["convenio"] for l in filtros.rodar("gp_convenios", com_periodo=False, unidade=False)]
    except comum.ConsultaFalhou:
        return []


def _motivos(filtros):
    try:
        return filtros.rodar("gm_motivos", com_periodo=False, unidade=False)
    except comum.ConsultaFalhou:
        return []


def consultar(slug, mes, unidade="", convenio="", motivo="", tipo=""):
    relatorio = RELATORIOS[slug]
    filtros = comum.Filtros(mes, unidade, convenio if relatorio.get("filtro_convenio") else "",
                            motivo if relatorio.get("filtro_motivo") else "",
                            tipo if relatorio.get("filtro_tipo", True) else "")
    inicio = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=PARALELO) as pool:
        futuros = [pool.submit(_executar, b, filtros) for b in relatorio["blocos"]]
        futuro_unidades = pool.submit(_unidades, filtros, relatorio["dimensao"])
        futuro_convenios = pool.submit(_convenios, filtros) if relatorio.get("filtro_convenio") else None
        futuro_motivos = pool.submit(_motivos, filtros) if relatorio.get("filtro_motivo") else None
        blocos = [f.result() for f in futuros]
        unidades = futuro_unidades.result()
        convenios = futuro_convenios.result() if futuro_convenios else []
        motivos = futuro_motivos.result() if futuro_motivos else []
    falhas = [b for b in blocos if b["dados"].get("erro")]
    sem_conexao = next((b for b in blocos if b["sem_conexao"]), None)
    return {
        "filtros": filtros,
        "blocos": blocos,
        "unidades": unidades,
        "convenios": convenios,
        "motivos": motivos,
        "ms_total": (time.perf_counter() - inicio) * 1000,
        "falhas": len(falhas),
        "sem_conexao": sem_conexao["dados"] if sem_conexao else None,
    }


def menu_relatorios(ativo=""):
    return [
        {"slug": s, "titulo": r["titulo"], "icone": r["icone"], "href": f"/reports/{s}", "ativo": s == ativo}
        for s, r in RELATORIOS.items()
    ]


def _carga_ativa():
    from ..conciliacao import banco

    try:
        return banco.carga_ativa()
    except Exception:  # noqa: BLE001 -- sem Postgres a página mostra o CTA
        logger.exception("reports: carga ativa indisponível")
        return None


def gerar_pagina(usuario, slug, mes="", unidade="", convenio="", motivo="", tipo=""):
    if slug not in RELATORIOS:
        return None, 404
    relatorio = RELATORIOS[slug]
    aviso_mes = None
    mes = (mes or "").strip()
    try:
        if mes or not relatorio.get("periodo_opcional"):
            comum.periodo(mes or comum.mes_padrao())
    except comum.PeriodoInvalido as falha:
        aviso_mes = f"{falha}. Mostrando o mês padrão."
        mes = ""
    if not relatorio.get("periodo_opcional"):
        mes = mes or comum.mes_padrao()

    carga = None
    if relatorio.get("fonte") == "planilha":
        carga = _carga_ativa()
        if not carga:
            html = layout.render(
                "reports/relatorio.html", relatorio["titulo"], usuario, f"/reports/{slug}",
                relatorio=relatorio, slug=slug, abas=menu_relatorios(slug), aviso_mes=None, sem_carga=True,
                filtros=comum.Filtros(""), blocos=[], unidades=[], convenios=[], motivos=[], ms_total=0, falhas=0,
                sem_conexao=None, carga=None,
            )
            return html, 200
    ctx = consultar(slug, mes, unidade, convenio, motivo, tipo)
    ctx["carga"] = carga
    html = layout.render(
        "reports/relatorio.html",
        relatorio["titulo"],
        usuario,
        f"/reports/{slug}",
        relatorio=relatorio,
        slug=slug,
        abas=menu_relatorios(slug),
        aviso_mes=aviso_mes,
        **ctx,
    )
    return html, 200
