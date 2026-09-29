"""Cruza cada linha da carga ativa com a conta do ERP -- e valida o faturado.

Chave: protocolo (CAPPAYMENT.CLI_PROTOCOENTREGA) + nome do paciente. Um
protocolo é uma conta de lote com vários pacientes, e cada linha da planilha é
UMA admissão do paciente nessa conta. O faturado do ERP é
SUM(UNITPRICE × (QUANTITY − COVERAGEQUANTITY)) -- ver sql_oracle.py.

Para cada linha, na ordem: a admissão (ainda não usada) cujo faturado bate;
a versão de trabalho da conta (CAPPAYMENTITEMWORK) que bate; o total do par;
senão, a admissão mais próxima, como divergente.

Situações:
  CONCILIADO            faturado da planilha = faturado do ERP (±R$ 1)
  DIVERGENTE            paciente achado na conta, nenhum valor bate
  PACIENTE NÃO ACHADO   o protocolo existe no ERP, o paciente não está nele
  PROTOCOLO NÃO ACHADO  nenhuma conta com esse protocolo
  SEM PROTOCOLO         vazio, "-", "0" ou curto demais para ser protocolo
"""

import collections
import decimal
import json
import logging
import re

from ..reports import fonte
from . import banco, regras

logger = logging.getLogger(__name__)

CONCILIADO = "CONCILIADO"
DIVERGENTE = "DIVERGENTE"
PACIENTE_NAO_ACHADO = "PACIENTE NÃO ACHADO"
PROTOCOLO_NAO_ACHADO = "PROTOCOLO NÃO ACHADO"
SEM_PROTOCOLO = "SEM PROTOCOLO"
SITUACOES = [CONCILIADO, DIVERGENTE, PACIENTE_NAO_ACHADO, PROTOCOLO_NAO_ACHADO, SEM_PROTOCOLO]

TOLERANCIA = decimal.Decimal("1.00")
LOTE = 900
_TRATAMENTO = re.compile(r"^(SRA?|DRA?|SR)\.?\s+")


def protocolo_valido(protocolo):
    """Protocolo normalizado como no ERP (sql_oracle._PROTOCOLO), ou None se não for protocolo.

    '01340288' e '1340288' são o mesmo; '330230297758-0' é '330230297758_0'.
    """
    p = (protocolo or "").strip().replace("-", "_").lstrip("0")
    return p if len(p) >= 4 else None


def nome(paciente):
    """'Sra. Fulana de Tal ' -> 'FULANA DE TAL': o ERP guarda tratamento e espaço sobrando."""
    return _TRATAMENTO.sub("", regras.chave(paciente))


def buscar_erp(protocolos):
    """{(protocolo, nome): [admissão, ...]} e o conjunto de protocolos achados.

    Cada admissão: id_admissao, id_conta, unidade, operadora, faturado (item),
    work (faturado na versão de trabalho) e glosa_iw.
    """
    por_admissao, achados = {}, set()
    lista = sorted(protocolos)
    for inicio in range(0, len(lista), LOTE):
        lote = {"PROTOCOLOS": lista[inicio:inicio + LOTE]}
        for l in fonte.rodar("conciliacao_protocolos", lote):
            achados.add(l["protocolo"])
            chave_ = (l["protocolo"], nome(l["paciente"]), l["id_admissao"])
            adm = por_admissao.setdefault(chave_, {
                "id_admissao": l["id_admissao"], "id_paciente": l.get("id_paciente"), "id_conta": l["id_conta"],
                "tipo_atendimento": l.get("tipo_atendimento"),
                "unidade": l["unidade"], "operadora": l["operadora"], "faturado": regras.ZERO, "work": regras.ZERO,
                "glosa_iw": regras.ZERO})
            adm["faturado"] += regras.zero(l["faturado"])
            adm["glosa_iw"] += regras.zero(l["glosa_iw"])
        for l in fonte.rodar("conciliacao_protocolos_work", lote):
            adm = por_admissao.get((l["protocolo"], nome(l["paciente"]), l["id_admissao"]))
            if adm:
                adm["work"] += regras.zero(l["faturado"])
    pares = collections.defaultdict(list)
    for (protocolo, paciente, _), adm in por_admissao.items():
        pares[(protocolo, paciente)].append(adm)
    return dict(pares), achados


def _bate(a, b):
    return abs(regras.zero(a) - regras.zero(b)) <= TOLERANCIA


def _casar(valor, admissoes, usadas):
    """(situação, regra, admissão, faturado_erp) para uma linha da planilha."""
    livres = [a for a in admissoes if a["id_admissao"] not in usadas] + \
             [a for a in admissoes if a["id_admissao"] in usadas]
    for adm in livres:
        if _bate(valor, adm["faturado"]):
            return CONCILIADO, "admissão", adm, adm["faturado"]
    for adm in livres:
        if adm["work"] and _bate(valor, adm["work"]):
            return CONCILIADO, "versão de trabalho", adm, adm["work"]
    total = sum(a["faturado"] for a in admissoes)
    if len(admissoes) > 1 and _bate(valor, total):
        return CONCILIADO, "total do paciente", None, total
    perto = min(livres, key=lambda a: abs(regras.zero(valor) - a["faturado"]))
    return DIVERGENTE, "mais próxima", perto, perto["faturado"]


def classificar(linhas, pares, achados):
    """Linhas da planilha + admissões do ERP -> list[dict] do cruzamento. Puro."""
    grupos = collections.defaultdict(list)
    saida = []
    for linha in linhas:
        protocolo = protocolo_valido(linha.get("protocolo"))
        if not protocolo:
            saida.append({"linha": linha["linha"], "situacao": SEM_PROTOCOLO, "principal": True})
        elif protocolo not in achados:
            saida.append({"linha": linha["linha"], "situacao": PROTOCOLO_NAO_ACHADO, "principal": True})
        else:
            grupos[(protocolo, nome(linha.get("paciente")))].append(linha)
    for chave_, grupo in grupos.items():
        admissoes = pares.get(chave_)
        if not admissoes:
            saida += [{"linha": l["linha"], "situacao": PACIENTE_NAO_ACHADO, "principal": True} for l in grupo]
            continue
        usadas = set()
        for l in sorted(grupo, key=lambda x: x["linha"]):
            valor = regras.zero(l.get("valor_faturado"))
            situacao, regra, adm, faturado = _casar(valor, admissoes, usadas)
            marca = adm["id_admissao"] if adm else "total"
            # faturado_erp e glosa_iw somam uma vez por admissão
            principal = marca not in usadas
            usadas.add(marca)
            base = adm or admissoes[0]
            saida.append({
                "linha": l["linha"], "situacao": situacao, "regra": regra,
                "id_conta": base["id_conta"], "id_admissao": adm["id_admissao"] if adm else None,
                "id_paciente": base.get("id_paciente"), "tipo_atendimento": base.get("tipo_atendimento"),
                "unidade_erp": base["unidade"], "operadora_erp": base["operadora"], "faturado_erp": faturado,
                "glosa_iw": adm["glosa_iw"] if adm else sum(a["glosa_iw"] for a in admissoes),
                "diferenca": valor - faturado, "principal": principal,
            })
    return saida


def buscar_por_competencia(competencias):
    """{(nome, competência): [admissão, ...]} das contas dessas competências."""
    pares = collections.defaultdict(list)
    for l in fonte.rodar("conciliacao_competencias", {"COMPETENCIAS": sorted(competencias)}):
        competencia = l["competencia"].date() if hasattr(l["competencia"], "date") else l["competencia"]
        pares[(nome(l["paciente"]), competencia)].append({
            "id_admissao": l["id_admissao"], "id_paciente": l.get("id_paciente"), "id_conta": l["id_conta"],
            "tipo_atendimento": l.get("tipo_atendimento"),
            "unidade": l["unidade"], "operadora": l["operadora"], "faturado": regras.zero(l["faturado"]),
            "work": regras.ZERO,
            "glosa_iw": regras.zero(l["glosa_iw"]), "protocolo": l["protocolo"]})
    return pares


def recasar_sem_protocolo(linhas, resultado, por_competencia):
    """Segunda passada: linha sem protocolo achado que bate por paciente + competência + valor
    vira CONCILIADO (regra 'paciente + competência'). As outras ficam como estavam."""
    por_linha = {l["linha"]: l for l in linhas}
    usadas = set()
    for r in resultado:
        if r["situacao"] not in (PROTOCOLO_NAO_ACHADO, SEM_PROTOCOLO):
            continue
        l = por_linha[r["linha"]]
        admissoes = por_competencia.get((nome(l.get("paciente")), l.get("competencia")))
        if not admissoes:
            continue
        valor = regras.zero(l.get("valor_faturado"))
        adm = next((a for a in admissoes if a["id_admissao"] not in usadas and _bate(valor, a["faturado"])), None)
        if adm is None:
            continue
        usadas.add(adm["id_admissao"])
        r.update({"situacao": CONCILIADO, "regra": "paciente + competência", "id_conta": adm["id_conta"],
                  "id_paciente": adm.get("id_paciente"), "tipo_atendimento": adm.get("tipo_atendimento"),
                  "id_admissao": adm["id_admissao"], "unidade_erp": adm["unidade"],
                  "operadora_erp": adm["operadora"], "faturado_erp": adm["faturado"],
                  "glosa_iw": adm["glosa_iw"], "diferenca": valor - adm["faturado"], "principal": True,
                  "protocolo_erp": adm["protocolo"]})
    return resultado


COLUNAS = ["linha", "situacao", "regra", "id_conta", "id_admissao", "unidade_erp", "operadora_erp",
           "faturado_erp", "glosa_iw", "diferenca", "principal", "protocolo_erp", "id_paciente",
           "tipo_atendimento"]


def executar(carga_id=None):
    """Cruza a carga (a ativa, por padrão) e grava. Devolve o resumo por situação."""
    carga = banco.obter_carga(carga_id) if carga_id else banco.carga_ativa()
    if not carga:
        raise LookupError("nenhuma carga para cruzar")
    carga_id = carga["id"]
    linhas = banco.consultar(
        "SELECT linha, protocolo, paciente, competencia, valor_faturado FROM conciliacao.glosa_linha "
        "WHERE carga_id = %s", (carga_id,), "linhas para cruzar",
    )
    protocolos = {p for p in (protocolo_valido(l["protocolo"]) for l in linhas) if p}
    pares, achados = buscar_erp(protocolos)
    resultado = classificar(linhas, pares, achados)
    soltas = {r["linha"] for r in resultado if r["situacao"] in (PROTOCOLO_NAO_ACHADO, SEM_PROTOCOLO)}
    competencias = {l["competencia"] for l in linhas if l["linha"] in soltas and l.get("competencia")}
    if competencias:
        resultado = recasar_sem_protocolo(linhas, resultado, buscar_por_competencia(competencias))
    resumo = collections.Counter(r["situacao"] for r in resultado)
    info = {"linhas": len(resultado), "protocolos": len(protocolos), "protocolos_achados": len(achados),
            "por_situacao": {s: resumo.get(s, 0) for s in SITUACOES}}
    with banco.conexao() as con:
        with con.cursor() as cur:
            cur.execute("DELETE FROM conciliacao.cruzamento WHERE carga_id = %s", (carga_id,))
            with cur.copy(f"COPY conciliacao.cruzamento (carga_id, {', '.join(COLUNAS)}) FROM STDIN") as copia:
                for r in resultado:
                    copia.write_row([carga_id, *[r.get(c) for c in COLUNAS]])
            cur.execute("UPDATE conciliacao.carga SET cruzada_em = now(), cruzamento = %s WHERE id = %s",
                        (json.dumps(info), carga_id))
    logger.info("conciliacao: carga %s cruzada: %s", carga_id, info["por_situacao"])
    return info
