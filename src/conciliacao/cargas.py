"""Carga da base de glosa: CSV -> linhas recalculadas no Postgres.

Cada upload é uma foto completa da planilha (decisão do time: a base é
cumulativa e as linhas antigas mudam de status). O fluxo:

1. lê e valida o CSV; coluna obrigatória faltando reprova o arquivo inteiro;
2. converte linha a linha; linha com erro é rejeitada e vai para o relatório,
   sem derrubar as outras;
3. recalcula as fórmulas da planilha (regras.calcular) e compara com o que a
   planilha trouxe nas colunas calculadas;
4. grava a carga, compara com a ativa anterior e ativa a nova numa transação.

O cruzamento com o ERP é um passo separado (cruzamento.py): depende do Oracle,
e a carga não pode falhar só porque a VPN caiu.
"""

import collections
import datetime
import decimal
import hashlib
import json
import logging

from . import banco, csv_leitor, layout_glosa, premissas, privacidade, regras

logger = logging.getLogger(__name__)

MAX_EXEMPLOS = 8
MAX_REJEITADAS = 300

# Por que cada coluna calculada costuma divergir, para o relatório da carga
EXPLICACAO = {
    "convenio_formula": "valor digitado por cima da fórmula (o time escolhe o convênio fórmula por filial)",
    "data_contratual": "data digitada por cima de entrega + prazo, ou calculada quando a entrega estava vazia",
    "prazo": "prazo digitado por cima do PRAZO_RECEBIMENTO",
    "prazo_recurso": "data digitada, ou convênio sem prazo de recurso cadastrado",
    "valor_liquido": "valor digitado por cima da fórmula ou convênio sem alíquota",
    "base_calculo_1": "valor digitado por cima de faturado − glosa",
    "base_calculo_2": "valor digitado por cima da fórmula",
    "status": "regra de status divergente — conferir datas de devolução e reapresentação",
    "status_glosa": "regra de status da glosa divergente — conferir os valores de recurso",
    "competencia": "período de atendimento fora do formato 'dd/mm/aaaa a dd/mm/aaaa'",
    "dias_atraso": "depende do STATUS e da data de referência (HOJE) usada na planilha",
    "aging": "depende dos dias de atraso",
}

TOTAIS = ["valor_faturado", "glosa", "valor_recursado", "glosa_acatada", "valor_recurso_bruto",
          "valor_recurso_liquido", "glosa_mantida"]

COLUNAS_BANCO = [
    "linha", *layout_glosa.DIGITADAS,
    "convenio_formula", "convenio_formula_de_para", "convenio_formula_manual", "competencia", "prazo",
    "data_contratual", "mes_previsao", "imposto", "valor_liquido", "base_calculo_1", "base_calculo_2",
    "status", "dias_atraso", "aging", "classificacao", "status_glosa", "prazo_recurso",
    "pendencias", "divergencias", "planilha", "paciente_codigo",
]


class CargaInvalida(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


def _json(valor):
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, (datetime.date, datetime.datetime)):
        return valor.isoformat()
    return valor


def identidade(linha):
    """Chave para comparar cargas: a mesma glosa de um paciente num período e protocolo."""
    return (regras.chave(linha.get("protocolo")), regras.chave(linha.get("paciente")),
            regras.chave(linha.get("periodo")), regras.chave(linha.get("convenio")))


def processar(conteudo, premissas_, data_referencia):
    """CSV -> (linhas calculadas, relatório). Puro: não toca no banco."""
    try:
        cabecalho, corpo, linha_cab = csv_leitor.ler_linhas(conteudo)
    except csv_leitor.CsvInvalido as falha:
        raise CargaInvalida(str(falha), "Exporte a aba BASE OPALUS inteira, com a linha de cabeçalho.") from falha
    indice, faltando, desconhecidas = layout_glosa.mapear(cabecalho)
    if faltando:
        raise CargaInvalida(
            f"faltam colunas obrigatórias: {', '.join(faltando)}",
            "Confira se o CSV é da aba BASE OPALUS e se o cabeçalho não foi alterado.",
        )

    linhas, rejeitadas = [], []
    divergencias = collections.Counter()
    exemplos = collections.defaultdict(list)
    pendencias = collections.Counter()
    faltas = collections.defaultdict(set)
    classificacoes = collections.Counter()
    manual = 0

    for posicao, bruta in enumerate(corpo, start=linha_cab + 1):
        registro, erros = layout_glosa.converter(bruta, indice)
        if erros:
            if len(rejeitadas) < MAX_REJEITADAS:
                rejeitadas.append({"linha": posicao, "erros": erros,
                                   "empresa": registro.get("empresa"), "convenio": registro.get("convenio")})
            else:
                rejeitadas.append({"linha": posicao})
            continue
        calculada, pend = regras.calcular(registro, premissas_, data_referencia)
        calculada["linha"] = posicao
        calculada["paciente_codigo"] = privacidade.pseudonimo(calculada.get("paciente"))
        calculada["pendencias"] = pend
        calculada["divergencias"] = regras.divergencias(calculada)
        for p in pend:
            pendencias[p] += 1
            faltas[p].add(calculada.get("convenio_formula") if "prazo de receb" in p or "alíquota" in p
                          else calculada.get("convenio"))
        for campo in calculada["divergencias"]:
            divergencias[campo] += 1
            if len(exemplos[campo]) < MAX_EXEMPLOS:
                exemplos[campo].append({
                    "linha": posicao, "empresa": calculada.get("empresa"), "convenio": calculada.get("convenio"),
                    "app": _json(calculada.get(campo)), "planilha": _json(calculada.get(f"{campo}_planilha")),
                })
        manual += bool(calculada.get("convenio_formula_manual"))
        classificacoes[(calculada.get("classificacao_bruta") or "", calculada.get("classificacao") or "")] += 1
        linhas.append(calculada)

    comparaveis = {c for c in regras.COMPARAVEIS if c in indice}
    relatorio = {
        "linhas_lidas": len(corpo),
        "linhas": len(linhas),
        "rejeitadas": len(rejeitadas),
        "rejeitadas_amostra": rejeitadas[:MAX_REJEITADAS],
        "colunas_desconhecidas": desconhecidas,
        "colunas_calculadas_recebidas": sorted(comparaveis),
        "divergencias": [
            {"campo": c, "linhas": n, "explicacao": EXPLICACAO.get(c, ""), "exemplos": exemplos[c]}
            for c, n in divergencias.most_common()
        ],
        "pendencias": [{"pendencia": p, "linhas": n, "convenios": sorted(x for x in faltas[p] if x)}
                       for p, n in pendencias.most_common()],
        "convenio_formula_manual": manual,
        "classificacoes": [{"bruta": b, "canonica": c, "linhas": n}
                           for (b, c), n in sorted(classificacoes.items(), key=lambda x: -x[1])
                           if b and regras.chave(b) != regras.chave(c)],
        "totais": {c: float(sum(regras.zero(l.get(c)) for l in linhas)) for c in TOTAIS},
        "competencias": sorted({l["competencia"].isoformat() for l in linhas if l.get("competencia")}),
    }
    return linhas, relatorio


def comparar(atuais, anteriores):
    """O que mudou da carga anterior para esta: novas, removidas, status da glosa alterado."""
    antes = collections.defaultdict(list)
    for linha in anteriores:
        antes[identidade(linha)].append(linha)
    novas, mudou_status, mudou_valor = 0, collections.Counter(), 0
    exemplos = []
    for linha in atuais:
        fila = antes.get(identidade(linha))
        if not fila:
            novas += 1
            continue
        anterior = fila.pop(0)
        if (anterior.get("status_glosa") or "") != (linha.get("status_glosa") or ""):
            mudou_status[(anterior.get("status_glosa") or "—", linha.get("status_glosa") or "—")] += 1
            if len(exemplos) < MAX_EXEMPLOS:
                exemplos.append({"linha": linha["linha"], "convenio": linha.get("convenio"),
                                 "de": anterior.get("status_glosa"), "para": linha.get("status_glosa")})
        elif any(abs(regras.zero(anterior.get(c)) - regras.zero(linha.get(c))) > regras.CENTAVO
                 for c in ("glosa", "valor_recursado", "valor_recurso_liquido", "glosa_mantida")):
            mudou_valor += 1
    removidas = sum(len(f) for f in antes.values())
    return {
        "novas": novas, "removidas": removidas, "valores_alterados": mudou_valor,
        "status_alterado": [{"de": de, "para": para, "linhas": n} for (de, para), n in mudou_status.most_common()],
        "exemplos": exemplos,
    }


def _linhas_para_comparar(carga_id):
    return banco.consultar(
        "SELECT protocolo, paciente, periodo, convenio, status_glosa, glosa, valor_recursado, "
        "valor_recurso_liquido, glosa_mantida FROM conciliacao.glosa_linha WHERE carga_id = %s",
        (carga_id,), "linhas da carga anterior",
    )


def _valor_banco(linha, coluna):
    if coluna == "planilha":
        return json.dumps({k[:-9]: _json(v) for k, v in linha.items() if k.endswith("_planilha")})
    if coluna in ("pendencias", "divergencias"):
        return list(linha.get(coluna) or [])
    return linha.get(coluna)


def gravar(conteudo, arquivo, data_referencia, autor=None, tipo="glosa"):
    """Processa e grava; devolve (carga_id, relatório). A carga nova fica ativa."""
    banco.garantir_schema()
    premissas_ = premissas.carregar()
    if not premissas_.de_para or not premissas_.prazo:
        raise CargaInvalida("premissas não carregadas",
                            "Rode `make conciliacao ARGS=premissas` ou envie os CSVs em Conciliação › Premissas.")
    sha = hashlib.sha256(conteudo).hexdigest()
    linhas, relatorio = processar(conteudo, premissas_, data_referencia)
    if not linhas:
        raise CargaInvalida("nenhuma linha válida", "Todas as linhas foram rejeitadas; veja os motivos no arquivo.")

    anterior = banco.carga_ativa(tipo)
    if anterior:
        relatorio["comparacao"] = comparar(linhas, _linhas_para_comparar(anterior["id"]))
        relatorio["comparacao"]["carga_anterior"] = anterior["id"]

    with banco.conexao() as con:
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO conciliacao.carga (tipo, arquivo, sha256, autor, data_referencia, linhas, rejeitadas, "
                "relatorio) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                (tipo, arquivo, sha, autor, data_referencia, len(linhas), relatorio["rejeitadas"],
                 json.dumps(relatorio, default=_json)),
            )
            carga_id = cur.fetchone()[0]
            with cur.copy(
                f"COPY conciliacao.glosa_linha (carga_id, {', '.join(COLUNAS_BANCO)}) FROM STDIN"
            ) as copia:
                for linha in linhas:
                    copia.write_row([carga_id, *[_valor_banco(linha, c) for c in COLUNAS_BANCO]])
            cur.execute("UPDATE conciliacao.carga SET ativa = false WHERE tipo = %s AND ativa", (tipo,))
            cur.execute("UPDATE conciliacao.carga SET ativa = true WHERE id = %s", (carga_id,))
    logger.info("conciliacao: carga %s gravada (%s linhas, %s rejeitadas)",
                carga_id, len(linhas), relatorio["rejeitadas"])
    return carga_id, relatorio


def listar(tipo="glosa", limite=30):
    return banco.consultar(
        "SELECT id, arquivo, autor, criada_em, data_referencia, linhas, rejeitadas, ativa, cruzada_em, "
        "relatorio->'totais' AS totais FROM conciliacao.carga WHERE tipo = %s ORDER BY id DESC LIMIT %s",
        (tipo, limite), "cargas",
    )


def obter(carga_id):
    return banco.um("SELECT * FROM conciliacao.carga WHERE id = %s", (carga_id,), f"carga {carga_id}")


def ativar(carga_id, tipo="glosa"):
    """Volta uma carga antiga a ser a ativa (desfaz um upload errado)."""
    with banco.conexao() as con:
        con.execute("UPDATE conciliacao.carga SET ativa = false WHERE tipo = %s AND ativa", (tipo,))
        con.execute("UPDATE conciliacao.carga SET ativa = true WHERE id = %s AND tipo = %s", (carga_id, tipo))
