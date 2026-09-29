"""Páginas /conciliacao/*: cargas, planilha × ERP, premissas e regras."""

import datetime
import inspect
import logging

from .. import catalogo, layout
from ..reports import comum, fonte
from . import banco, cargas, cruzamento, premissas, privacidade, regras, tiss, tiss_cruzamento, tiss_divergencias

logger = logging.getLogger(__name__)

TAMANHO_MAXIMO = 20 * 1024 * 1024


def abas(ativo):
    itens = [("tiss", "Retornos TISS (xml)", "file-code-2"), ("cargas", "Cargas (planilha)", "upload"),
             ("glosa-erp", "Qualidade do cruzamento", "git-compare-arrows"),
             ("premissas", "Premissas", "sliders-horizontal"), ("regras", "Regras da planilha", "function-square")]
    return [{"slug": s, "titulo": t, "icone": i, "href": f"/conciliacao/{s}", "ativo": s == ativo}
            for s, t, i in itens]


def _render(template, titulo, usuario, slug, **ctx):
    return layout.render(template, titulo, usuario, f"/conciliacao/{slug}", abas=abas(slug),
                         abas_conciliacao=True, **ctx)


def _erro_banco(template, titulo, usuario, slug, falha):
    return _render(template, titulo, usuario, slug, erro_banco=str(getattr(falha, "causa", falha))), 502


# --------------------------------------------------------------------------
# Retornos TISS (XML de volta da operadora)
# --------------------------------------------------------------------------


def pagina_tiss(usuario, arquivo_id=None, aviso=None, erro=None):
    try:
        lista = tiss_cruzamento.listar()
        selecionado = next((a for a in lista if a["id"] == arquivo_id), None) if arquivo_id else \
            (lista[0] if lista else None)
        guias = banco.consultar(
            "SELECT guia_prestador, protocolo, situacao, regra, id_conta, id_admissao, id_paciente, id_orcamento, "
            "faturado_erp, informado, liberado, glosa, motivo_principal FROM conciliacao.tiss_guia "
            "WHERE arquivo_id = %s ORDER BY glosa DESC, guia_prestador", (selecionado["id"],),
            "guias do retorno") if selecionado else []
    except catalogo.ConsultaFalhou as falha:
        return _erro_banco("conciliacao/tiss.html", "Retornos TISS (xml)", usuario, "tiss", falha)
    return _render("conciliacao/tiss.html", "Retornos TISS (xml)", usuario, "tiss", lista=lista,
                   arquivo=selecionado, guias=guias, aviso=aviso, erro=erro), 200


def _xmls(nome, conteudo):
    """(nome, bytes) de cada XML do upload: o próprio arquivo ou os de dentro de um .zip."""
    import io
    import zipfile

    if nome.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            return [(n.rsplit("/", 1)[-1], z.read(n)) for n in z.namelist()
                    if n.lower().endswith(".xml") and not n.startswith("__MACOSX")]
    return [(nome, conteudo)]


def receber_tiss(arquivos, autor=None):
    """[(nome, bytes)] -> (id do último arquivo gravado, aviso, erro)."""
    gravados, repetidos, recusados, ultimo = [], [], [], None
    for nome, conteudo in arquivos:
        if len(conteudo) > TAMANHO_MAXIMO:
            recusados.append(f"{nome}: maior que {TAMANHO_MAXIMO // (1024 * 1024)} MB")
            continue
        try:
            for nome_xml, xml in _xmls(nome, conteudo):
                try:
                    arquivo_id, resumo, repetido = tiss_cruzamento.gravar(xml, nome_xml, autor)
                except tiss_cruzamento.ArquivoRecusado as falha:
                    recusados.append(f"{nome_xml}: {falha.motivo}")
                    continue
                ultimo = arquivo_id
                (repetidos if repetido else gravados).append(nome_xml)
        except Exception as falha:  # zip corrompido, Oracle fora
            recusados.append(f"{nome}: {falha}")
    partes = []
    if gravados:
        partes.append(f"{len(gravados)} retorno(s) carregado(s)")
    if repetidos:
        partes.append(f"{len(repetidos)} já estava(m) carregado(s)")
    erro = {"motivo": f"{len(recusados)} arquivo(s) recusado(s)", "detalhe": "; ".join(recusados[:5])} \
        if recusados else None
    return ultimo, (". ".join(partes) + ".") if partes else None, erro


def divergencias_md(arquivo_id):
    return tiss_divergencias.gerar(arquivo_id)


def excluir_tiss(arquivo_id):
    return tiss_cruzamento.excluir(arquivo_id)


# --------------------------------------------------------------------------
# Cargas
# --------------------------------------------------------------------------


def pagina_cargas(usuario, carga_id=None, aviso=None, erro=None):
    try:
        lista = cargas.listar()
        selecionada = cargas.obter(carga_id) if carga_id else (
            cargas.obter(next((c["id"] for c in lista if c["ativa"]), lista[0]["id"])) if lista else None)
        n_premissas = premissas.contagens()
    except catalogo.ConsultaFalhou as falha:
        return _erro_banco("conciliacao/cargas.html", "Cargas", usuario, "cargas", falha)
    return _render("conciliacao/cargas.html", "Cargas", usuario, "cargas", lista=lista, carga=selecionada,
                   hoje=datetime.date.today(), aviso=aviso, erro=erro,
                   sem_premissas=not n_premissas.get("de_para") or not n_premissas.get("prazo")), 200


def receber_upload(conteudo, arquivo, data_referencia, autor):
    """Grava a carga e tenta cruzar. Devolve (carga_id, aviso, erro)."""
    if not conteudo:
        return None, None, {"motivo": "arquivo vazio", "detalhe": "Escolha o CSV exportado da aba BASE OPALUS."}
    if len(conteudo) > TAMANHO_MAXIMO:
        return None, None, {"motivo": "arquivo grande demais", "detalhe": "O limite é 20 MB."}
    try:
        referencia = datetime.date.fromisoformat(data_referencia) if data_referencia else datetime.date.today()
    except ValueError:
        return None, None, {"motivo": "data de referência inválida", "detalhe": data_referencia}
    try:
        carga_id, relatorio = cargas.gravar(conteudo, arquivo, referencia, autor)
    except cargas.CargaInvalida as falha:
        return None, None, {"motivo": falha.motivo, "detalhe": falha.detalhe}
    aviso = f"Carga #{carga_id} ativa: {relatorio['linhas']} linhas, {relatorio['rejeitadas']} rejeitadas."
    try:
        info = cruzamento.executar(carga_id)
        aviso += f" Cruzamento com o ERP: {info['por_situacao'][cruzamento.CONCILIADO]} linhas conciliadas."
    except (fonte.ConsultaFalhou, comum.ConsultaFalhou) as falha:
        aviso += f" Cruzamento com o ERP não rodou ({falha.motivo}); use Reconciliar quando o Oracle voltar."
    return carga_id, aviso, None


# --------------------------------------------------------------------------
# Qualidade do cruzamento
# --------------------------------------------------------------------------

SQL_POR_SITUACAO = """
SELECT x.situacao, COUNT(*) AS linhas, COALESCE(SUM(g.valor_faturado), 0) AS faturado,
       COALESCE(SUM(g.glosa), 0) AS glosa,
       COALESCE(SUM(x.faturado_erp) FILTER (WHERE x.principal), 0) AS faturado_erp,
       COALESCE(SUM(x.glosa_iw) FILTER (WHERE x.principal), 0) AS glosa_iw
  FROM conciliacao.cruzamento x
  JOIN conciliacao.glosa_linha g ON g.carga_id = x.carga_id AND g.linha = x.linha
 WHERE x.carga_id = %(carga)s
 GROUP BY x.situacao
"""

SQL_POR_COMPETENCIA = """
SELECT g.competencia, COALESCE(SUM(g.glosa), 0) AS glosa_planilha,
       COALESCE(SUM(x.glosa_iw) FILTER (WHERE x.principal), 0) AS glosa_iw,
       COUNT(*) FILTER (WHERE x.situacao = 'CONCILIADO') AS conciliadas, COUNT(*) AS linhas
  FROM conciliacao.glosa_linha g
  LEFT JOIN conciliacao.cruzamento x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE g.carga_id = %(carga)s AND g.competencia IS NOT NULL
 GROUP BY g.competencia ORDER BY g.competencia
"""

SQL_POR_CONVENIO = """
SELECT g.convenio, COUNT(*) AS linhas,
       COUNT(*) FILTER (WHERE x.situacao = 'CONCILIADO') AS conciliadas,
       COUNT(*) FILTER (WHERE x.situacao = 'DIVERGENTE') AS divergentes,
       COUNT(*) FILTER (WHERE x.situacao NOT IN ('CONCILIADO', 'DIVERGENTE')) AS nao_achadas,
       COALESCE(SUM(x.diferenca) FILTER (WHERE x.principal AND x.situacao = 'DIVERGENTE'), 0) AS diferenca
  FROM conciliacao.glosa_linha g
  JOIN conciliacao.cruzamento x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE g.carga_id = %(carga)s
 GROUP BY g.convenio ORDER BY COUNT(*) - COUNT(*) FILTER (WHERE x.situacao = 'CONCILIADO') DESC
 LIMIT 15
"""

TOM_SITUACAO = {cruzamento.CONCILIADO: "teal", cruzamento.DIVERGENTE: "amber",
                cruzamento.PACIENTE_NAO_ACHADO: "violet", cruzamento.PROTOCOLO_NAO_ACHADO: "coral",
                cruzamento.SEM_PROTOCOLO: "navy"}
EXPLICA_SITUACAO = {
    cruzamento.CONCILIADO: "faturado igual ao do ERP: preço × (qtd − qtd coberta), ±R$ 1",
    cruzamento.DIVERGENTE: "paciente achado na conta, nenhuma admissão com o mesmo valor",
    cruzamento.PACIENTE_NAO_ACHADO: "protocolo existe no ERP, paciente não está na conta",
    cruzamento.PROTOCOLO_NAO_ACHADO: "nem o protocolo nem paciente + competência + valor acham a conta",
    cruzamento.SEM_PROTOCOLO: "protocolo vazio, '-', '0' ou texto (CORREIOS, PENDENTE)",
}


def pagina_glosa_erp(usuario, aviso=None):
    try:
        carga = banco.carga_ativa()
        if not carga or not carga.get("cruzada_em"):
            return _render("conciliacao/glosa_erp.html", "Qualidade do cruzamento", usuario, "glosa-erp", carga=carga,
                           sem_cruzamento=True, aviso=aviso), 200
        p = {"carga": carga["id"]}
        por_situacao = {l["situacao"]: l for l in banco.consultar(SQL_POR_SITUACAO, p, "cruzamento por situação")}
        competencias = banco.consultar(SQL_POR_COMPETENCIA, p, "cruzamento por competência")
        convenios = banco.consultar(SQL_POR_CONVENIO, p, "cruzamento por convênio")
    except catalogo.ConsultaFalhou as falha:
        return _erro_banco("conciliacao/glosa_erp.html", "Qualidade do cruzamento", usuario, "glosa-erp", falha)

    total = sum(l["linhas"] for l in por_situacao.values())
    cards = []
    for sit in cruzamento.SITUACOES:
        l = por_situacao.get(sit, {"linhas": 0, "faturado": 0})
        cards.append({"rotulo": sit.capitalize(), "valor": l["linhas"], "formato": "int",
                      "tom": TOM_SITUACAO[sit], "barra": comum.pct(l["linhas"], total),
                      "icone": {"teal": "check-check", "amber": "scale", "violet": "user-x", "coral": "file-x",
                                "navy": "circle-slash"}[TOM_SITUACAO[sit]],
                      "hint": EXPLICA_SITUACAO[sit]})
    rotulos = [comum.rotulo_mes(c["competencia"]) for c in competencias]
    grafico = comum.grafico("barras-linha", rotulos, [
        {"nome": "Glosa na planilha", "tom": "coral", "valores": [c["glosa_planilha"] for c in competencias]},
        {"nome": "Glosa no IW (ERP)", "tom": "navy", "valores": [c["glosa_iw"] for c in competencias]},
        {"nome": "% conciliado", "tom": "teal", "tipo": "linha", "eixo": "pct",
         "valores": [comum.pct(c["conciliadas"], c["linhas"]) or 0 for c in competencias]},
    ])
    glosa_planilha = sum(comum.num(l["glosa"]) for l in por_situacao.values())
    glosa_iw = sum(comum.num(l["glosa_iw"]) for l in por_situacao.values())
    return _render(
        "conciliacao/glosa_erp.html", "Qualidade do cruzamento", usuario, "glosa-erp", carga=carga, cards=cards,
        grafico=grafico, convenios=convenios, situacoes=cruzamento.SITUACOES, tom_situacao=TOM_SITUACAO,
        aviso=aviso,
        glosa_planilha=glosa_planilha, glosa_iw=glosa_iw,
    ), 200


def reconciliar():
    try:
        info = cruzamento.executar()
    except LookupError:
        return None, {"motivo": "nenhuma carga ativa", "detalhe": "Carregue a planilha em Conciliação › Cargas."}
    except (fonte.ConsultaFalhou, comum.ConsultaFalhou) as falha:
        return None, {"motivo": falha.motivo, "detalhe": falha.dica}
    return f"Cruzamento refeito: {info['por_situacao'][cruzamento.CONCILIADO]} de {info['linhas']} linhas conciliadas.", None


# --------------------------------------------------------------------------
# Premissas
# --------------------------------------------------------------------------


def pagina_premissas(usuario, tipo="", aviso=None, erro=None, editar=None, rascunho=None):
    tipo = tipo if tipo in premissas.TIPOS else "imposto"
    try:
        contagens = premissas.contagens()
        linhas = premissas.listar(tipo)
        carga = banco.carga_ativa()
        pendencias = []
        if carga:
            rel = banco.um("SELECT relatorio FROM conciliacao.carga WHERE id = %s", (carga["id"],))["relatorio"]
            pendencias = rel.get("pendencias", [])
            manual = rel.get("convenio_formula_manual", 0)
        else:
            manual = 0
    except catalogo.ConsultaFalhou as falha:
        return _erro_banco("conciliacao/premissas.html", "Premissas", usuario, "premissas", falha)
    definicao = premissas.TIPOS[tipo]
    sincronizacao = None
    if tipo == "motivo_tiss":
        try:
            sincronizacao = tiss.ultima_sincronizacao()
        except catalogo.ConsultaFalhou:
            sincronizacao = None
    return _render("conciliacao/premissas.html", "Premissas", usuario, "premissas", sincronizacao=sincronizacao,
                   tipos=premissas.TIPOS,
                   tipo=tipo, definicao=definicao, colunas=[c for c, _ in definicao["colunas"]], linhas=linhas,
                   editavel=tipo in premissas.EDITAVEIS, editar=editar, rascunho=rascunho or {},
                   percentuais=premissas.PERCENTUAIS,
                   contagens=contagens, pendencias=pendencias, manual=manual, carga=carga,
                   aviso=aviso, erro=erro), 200


AVISO_RECALCULO = " Carregue a planilha de novo para recalcular com as premissas novas."


def salvar_linha(tipo, campos, id_linha=None, autor=None):
    """(aviso, erro) de incluir (id_linha None) ou alterar uma linha de premissa."""
    try:
        registro = premissas.ler_formulario(tipo, campos)
        if id_linha is None:
            premissas.criar(tipo, registro, autor)
        else:
            premissas.atualizar(tipo, id_linha, registro, autor)
    except premissas.PremissaInvalida as falha:
        return None, {"motivo": falha.motivo, "detalhe": falha.detalhe}
    except catalogo.ConsultaFalhou as falha:
        return None, {"motivo": "o banco não aceitou a alteração", "detalhe": str(falha)}
    return ("Linha incluída." if id_linha is None else "Linha alterada.") + AVISO_RECALCULO, None


def excluir_linha(tipo, id_linha, autor=None):
    try:
        premissas.excluir(tipo, id_linha, autor)
    except premissas.PremissaInvalida as falha:
        return None, {"motivo": falha.motivo, "detalhe": falha.detalhe}
    except catalogo.ConsultaFalhou as falha:
        return None, {"motivo": "o banco não aceitou a exclusão", "detalhe": str(falha)}
    return "Linha excluída." + AVISO_RECALCULO, None


def receber_premissa(tipo, conteudo):
    if tipo not in premissas.TIPOS:
        return None, {"motivo": f"tipo de premissa '{tipo}' não existe", "detalhe": ""}
    try:
        linhas, avisos = premissas.ler_csv(tipo, conteudo)
        premissas.gravar(tipo, linhas)
    except premissas.PremissaInvalida as falha:
        return None, {"motivo": falha.motivo, "detalhe": falha.detalhe}
    texto = f"{premissas.TIPOS[tipo]['titulo']}: {len(linhas)} linhas gravadas."
    if avisos:
        texto += f" {len(avisos)} avisos: " + "; ".join(avisos[:3])
    texto += " Carregue a planilha de novo para recalcular com as premissas novas."
    return texto, None


def sincronizar_tiss(autor):
    """Sincronização manual da Tabela 38 com a ANS. Devolve (aviso, erro)."""
    try:
        r = tiss.sincronizar(autor=autor)
    except tiss.SincronizacaoFalhou as falha:
        return None, {"motivo": falha.motivo, "detalhe": falha.detalhe}
    return (f"Tabela 38 sincronizada com a ANS: versão {r['versao']} (+ {r['versao_anterior'] or '—'}), "
            f"{r['vigentes']} códigos vigentes e {r['descontinuados']} descontinuados; "
            f"{r['novos']} novos, {r['alterados']} com descrição alterada."), None


# --------------------------------------------------------------------------
# Regras
# --------------------------------------------------------------------------

REGRAS = [
    ("CONVENIO FORMULA", regras.convenio_formula),
    ("COMPETENCIA", regras.competencia),
    ("PRAZO", regras.prazo),
    ("VALOR LIQUIDO PREVISTO / BASE CALCULO 2", regras.aliquota),
    ("STATUS", regras.status_recebimento),
    ("DIAS DE ATRASO", regras.dias_atraso),
    ("AGING", regras.faixa_aging),
    ("STATUS DA GLOSA", regras.status_glosa),
    ("DATA DE PRAZO P/ RECURSO", regras.prazo_recurso),
    ("CLASSIFICACAO", regras.normalizar_classificacao),
    ("Cruzamento com o ERP", cruzamento),
]


def pagina_regras(usuario):
    itens = [{"coluna": c, "funcao": getattr(f, "__name__", ""), "doc": inspect.getdoc(f) or ""} for c, f in REGRAS]
    return _render("conciliacao/regras.html", "Regras da planilha", usuario, "regras", regras=itens,
                   explicacoes=cargas.EXPLICACAO, status_glosa=regras.STATUS_GLOSA), 200
