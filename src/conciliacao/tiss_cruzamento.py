"""Grava o XML TISS de volta e casa cada guia (e item glosado) com o ERP.

Chaves, conferidas no protocolo 226689537 da CASSI:
  protocolo  numeroProtocolo = CAPPAYMENT.CLI_PROTOCOENTREGA (normalizado como em
             cruzamento.protocolo_valido / sql_oracle._PROTOCOLO)
  guia       numeroGuiaPrestador = CAPPAYMENT.ID + CAPADMISSION.ID ('80453' + '28169')
  valor      valorInformadoGuia = faturado do ERP na admissão, ao centavo
  senha      senha da guia = CAPBUDGET.AUTHORIZEXTCODE (o orçamento)
  item       o código do XML (TUSS/Simpro) não é o do ERP; casa por valor: a soma
             dos itens diários de um procedimento = cobrado do item mensal

Situações da guia: CONCILIADO (±R$ 1), DIVERGENTE, GUIA NÃO ACHADA, PROTOCOLO NÃO ACHADO.
"""

import collections
import decimal
import hashlib
import json
import logging

from ..reports import fonte
from . import banco, cruzamento, regras, tiss_xml

logger = logging.getLogger(__name__)

CONCILIADO = "CONCILIADO"
DIVERGENTE = "DIVERGENTE"
GUIA_NAO_ACHADA = "GUIA NÃO ACHADA"
PROTOCOLO_NAO_ACHADO = "PROTOCOLO NÃO ACHADO"
SITUACOES = [CONCILIADO, DIVERGENTE, GUIA_NAO_ACHADA, PROTOCOLO_NAO_ACHADO]
TOLERANCIA = decimal.Decimal("1.00")
TOLERANCIA_ITEM = decimal.Decimal("0.05")
LOTE = 900


class ArquivoRecusado(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


def _em_lotes(nome, chave, valores):
    lista, saida = sorted(valores), []
    for inicio in range(0, len(lista), LOTE):
        saida += fonte.rodar(nome, {chave: lista[inicio:inicio + LOTE]})
    return saida


def admissoes_erp(protocolos):
    """{protocolo normalizado: {id_conta: {id_admissao: dados}}} pela consulta da conciliação da planilha."""
    saida = collections.defaultdict(lambda: collections.defaultdict(dict))
    for l in _em_lotes("conciliacao_protocolos", "PROTOCOLOS", protocolos):
        adm = saida[l["protocolo"]][l["id_conta"]].setdefault(l["id_admissao"], {
            "id_admissao": l["id_admissao"], "id_paciente": l.get("id_paciente"),
            "tipo_atendimento": l.get("tipo_atendimento"), "unidade": l["unidade"], "operadora": l["operadora"],
            "faturado": regras.ZERO})
        adm["faturado"] += regras.zero(l["faturado"])
    return saida


def casar_guia(guia, contas, orcamentos_senha):
    """(situação, regra, id_conta, admissão) de uma guia. contas: {id_conta: {id_admissao: dados}}. Puro."""
    if not contas:
        return PROTOCOLO_NAO_ACHADO, None, None, None
    numero = guia.guia_prestador
    for id_conta, adms in contas.items():
        prefixo = str(id_conta)
        resto = numero[len(prefixo):] if numero.startswith(prefixo) else ""
        if resto.isdigit() and int(resto) in adms:
            adm = adms[int(resto)]
            return _situacao(guia, adm), "guia = conta + admissão", id_conta, adm
    for id_conta, adms in contas.items():
        for adm in adms.values():
            if abs(adm["faturado"] - guia.informado) <= TOLERANCIA:
                return CONCILIADO, "valor da admissão", id_conta, adm
    for orc in orcamentos_senha.get(guia.senha, []):
        for id_conta, adms in contas.items():
            if orc["id_admissao"] in adms:
                adm = adms[orc["id_admissao"]]
                return _situacao(guia, adm), "senha do orçamento", id_conta, adm
    return GUIA_NAO_ACHADA, None, None, None


def _situacao(guia, adm):
    return CONCILIADO if abs(adm["faturado"] - guia.informado) <= TOLERANCIA else DIVERGENTE


def casar_itens(itens, itens_erp):
    """{índice do item XML: id_item_erp} para os procedimentos com glosa. Puro.

    Soma os itens diários do mesmo procedimento e procura o item do ERP com o mesmo
    cobrado; senão, o de mesma quantidade e preço unitário.
    """
    grupos = collections.defaultdict(list)
    for n, i in enumerate(itens):
        grupos[(i.tabela, i.codigo)].append(n)
    livres = list(itens_erp)
    saida = {}
    for indices in grupos.values():
        if not any(itens[n].glosa > 0 for n in indices):
            continue
        qtd = sum((itens[n].quantidade for n in indices), regras.ZERO)
        valor = sum((itens[n].informado for n in indices), regras.ZERO)
        alvo = next((e for e in livres if abs(regras.zero(e["cobrado"]) - valor) <= TOLERANCIA_ITEM), None)
        if alvo is None and qtd:
            preco = valor / qtd
            alvo = next((e for e in livres if regras.zero(e["qtd"]) == qtd
                         and abs(regras.zero(e["preco"]) - preco) <= TOLERANCIA_ITEM), None)
        if alvo is not None:
            livres.remove(alvo)
            saida.update({n: alvo["id_item"] for n in indices})
    return saida


def _competencia(valor):
    return valor.date() if hasattr(valor, "date") else valor


def gravar(conteudo, arquivo, autor=None):
    """Lê, grava e casa um XML de volta. Devolve (id do arquivo, resumo, repetido)."""
    sha = hashlib.sha256(conteudo).hexdigest()
    banco.garantir_schema()
    existente = banco.um("SELECT id, resumo FROM conciliacao.tiss_arquivo WHERE sha256 = %s", (sha,),
                         "arquivo TISS já carregado")
    if existente:
        return existente["id"], existente["resumo"], True
    try:
        demo = tiss_xml.ler(conteudo)
    except tiss_xml.XmlInvalido as falha:
        raise ArquivoRecusado(falha.motivo, falha.detalhe) from falha

    protocolos = {p for p in (cruzamento.protocolo_valido(g.protocolo) for g in demo.guias) if p}
    erp = admissoes_erp(protocolos)
    senhas = {g.senha for g in demo.guias if g.senha}
    orcamentos = collections.defaultdict(list)
    for o in _em_lotes("tiss_orcamentos_senha", "SENHAS", senhas) if senhas else []:
        orcamentos[o["senha"]].append(o)
    casadas = []
    for g in demo.guias:
        contas = erp.get(cruzamento.protocolo_valido(g.protocolo) or "", {})
        casadas.append((g, *casar_guia(g, contas, orcamentos)))
    ids_conta = {c for _, _, _, c, _ in casadas if c}
    cabecalhos = {l["id_conta"]: l for l in _em_lotes("tiss_contas", "IDS", ids_conta)} if ids_conta else {}
    contas_glosa = {c for g, _, _, c, _ in casadas if c and g.glosa > 0}
    itens_erp = collections.defaultdict(list)
    for l in _em_lotes("tiss_itens_contas", "IDS", contas_glosa) if contas_glosa else []:
        itens_erp[(l["id_conta"], l["id_admissao"])].append(l)

    resumo = {"guias": len(demo.guias), "itens": sum(len(g.itens) for g in demo.guias),
              "protocolos": sorted({g.protocolo for g in demo.guias}),
              "por_situacao": dict(collections.Counter(s for _, s, _, _, _ in casadas)),
              "informado": str(demo.informado), "liberado": str(demo.liberado), "glosa": str(demo.glosa),
              "guias_com_glosa": sum(1 for g in demo.guias if g.glosa > 0), "itens_casados": 0}
    with banco.conexao() as con:
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO conciliacao.tiss_arquivo (tipo, sha256, arquivo, operadora_ans, operadora_nome, "
                "operadora_cnpj, numero_demonstrativo, data_emissao, padrao, autor, informado, liberado, glosa, "
                "resumo, conteudo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (demo.tipo, sha, arquivo, demo.operadora_ans, demo.operadora_nome, demo.operadora_cnpj, demo.numero,
                 demo.data_emissao, demo.padrao, autor, demo.informado, demo.liberado, demo.glosa, "{}", conteudo))
            arquivo_id = cur.fetchone()[0]
            for g, situacao, regra, id_conta, adm in casadas:
                orc = next((o["id_orcamento"] for o in orcamentos.get(g.senha, [])
                            if adm and o["id_admissao"] == adm["id_admissao"]), None)
                cab = cabecalhos.get(id_conta, {})
                cur.execute(
                    "INSERT INTO conciliacao.tiss_guia (arquivo_id, protocolo, guia_prestador, guia_operadora, senha, "
                    "carteira_hash, situacao_tiss, informado, processado, liberado, glosa, motivo_principal, motivos, "
                    "situacao, regra, id_conta, id_admissao, id_paciente, id_orcamento, tipo_atendimento, competencia, "
                    "unidade_erp, operadora_erp, faturado_erp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (arquivo_id, g.protocolo, g.guia_prestador, g.guia_operadora, g.senha, g.carteira_hash,
                     g.situacao, g.informado, g.processado, g.liberado, g.glosa, g.motivo_principal,
                     json.dumps(g.motivos, ensure_ascii=False), situacao, regra, id_conta,
                     adm and adm["id_admissao"], adm and adm["id_paciente"], orc, adm and adm["tipo_atendimento"],
                     _competencia(cab.get("competencia")), cab.get("unidade") or (adm and adm["unidade"]),
                     cab.get("operadora") or (adm and adm["operadora"]), adm and adm["faturado"]))
                guia_id = cur.fetchone()[0]
                casados = casar_itens(g.itens, itens_erp.get((id_conta, adm["id_admissao"]), [])) \
                    if adm and g.glosa > 0 else {}
                resumo["itens_casados"] += sum(1 for n in casados if g.itens[n].glosa > 0)
                with cur.copy("COPY conciliacao.tiss_item (guia_id, sequencial, data, tabela, codigo, descricao, "
                              "quantidade, informado, processado, liberado, glosa, motivo_principal, motivos, "
                              "id_item_erp) FROM STDIN") as copia:
                    for n, i in enumerate(g.itens):
                        copia.write_row([guia_id, i.sequencial, i.data, i.tabela, i.codigo, i.descricao, i.quantidade,
                                         i.informado, i.processado, i.liberado, i.glosa, i.motivo_principal,
                                         json.dumps(i.motivos), casados.get(n)])
            cur.execute("UPDATE conciliacao.tiss_arquivo SET resumo = %s WHERE id = %s",
                        (json.dumps(resumo, ensure_ascii=False), arquivo_id))
    logger.info("tiss: %s carregou o demonstrativo %s (%s): %s", autor or "anônimo", demo.numero,
                demo.operadora_nome, resumo["por_situacao"])
    return arquivo_id, resumo, False


def listar(limite=50):
    return banco.consultar(
        "SELECT id, arquivo, operadora_nome, operadora_ans, numero_demonstrativo, data_emissao, padrao, autor, "
        "recebido_em, informado, liberado, glosa, resumo FROM conciliacao.tiss_arquivo ORDER BY recebido_em DESC "
        "LIMIT %s", (limite,), "retornos TISS")


def excluir(arquivo_id):
    with banco.conexao() as con:
        n = con.execute("DELETE FROM conciliacao.tiss_arquivo WHERE id = %s", (arquivo_id,)).rowcount
    return n
