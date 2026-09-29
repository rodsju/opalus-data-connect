"""Análise de um orçamento por IA, para prevenir glosa. Sob demanda e gravada.

Reaproveita o cadastro de provedores (Setup › AI Providers) e o adaptador de
src/ia.py -- o mesmo caminho de ia.classificar: instruções próprias, resposta
num esquema pydantic, repetição só no que é transitório.

O que sai para o provedor: itens do orçamento e da fatura (recurso, categoria,
quantidade, preço), os desvios, os riscos por regras, o histórico de glosa da
operadora na planilha e os motivos TISS de referência. NUNCA o nome do paciente
-- ele aparece só pelo código ('P' + ID do ERP).

A resposta é conferida antes de gravar: item citado tem de estar no payload e
motivo TISS tem de existir na Tabela 38 sincronizada. Resposta que inventa item
ou código é recusada, não gravada.
"""

import hashlib
import json
import logging
from typing import Literal

from pydantic import BaseModel

from .. import ia, provedores
from ..conciliacao import banco

logger = logging.getLogger(__name__)

MAX_ITENS = 60
MAX_RISCOS = 8

INSTRUCOES = """Você é auditor de contas médicas de home care e trabalha para o prestador \
(Opalus). Recebe um orçamento autorizado pela operadora, os itens já faturados contra ele, os \
desvios entre os dois, riscos já apontados por regras e o histórico de glosas dessa operadora. \
Sua tarefa: apontar o que pode ser GLOSADO pela operadora quando esta conta for enviada, e o que \
fazer ANTES de enviar para evitar a glosa.

Regras:
- Use só os dados recebidos. Não invente valores, itens nem códigos.
- Em "item", repita o nome do recurso exatamente como aparece em itens[].recurso; deixe vazio quando \
o risco for do orçamento como um todo (senha, validade, documentação).
- Em "motivo_tiss", use um código de motivos_tiss_referencia (o motivo que a operadora usaria) ou \
deixe vazio.
- Priorize pelo valor em risco e pelo histórico da operadora. No máximo 8 riscos.
- "recomendacao" é uma ação concreta do faturamento/auditoria (ex.: ajustar quantidade à \
autorizada, pedir senha complementar, anexar prescrição), em uma frase.
- "resumo": duas ou três frases com o risco geral da conta.

Responda em português, SOMENTE com um objeto JSON exatamente neste formato (todos os campos são obrigatórios; use "" quando não houver valor):
{
  "resumo": "texto",
  "riscos": [
    {
      "tema": "quantidade | preço | item não orçado | senha/validade | documentação | cobertura | outro",
      "item": "nome do recurso exatamente como em itens[].recurso, ou \"\"",
      "motivo_tiss": "código de motivos_tiss_referencia, ou \"\"",
      "evidencia": "o dado que sustenta o risco",
      "recomendacao": "ação antes de enviar a conta",
      "severidade": "alta | media | baixa"
    }
  ]
}
Em "tema" e "severidade" use exatamente um dos valores listados (sem a barra vertical)."""


class RiscoIA(BaseModel):
    tema: Literal["quantidade", "preço", "item não orçado", "senha/validade", "documentação", "cobertura", "outro"]
    item: str
    motivo_tiss: str
    evidencia: str
    recomendacao: str
    severidade: Literal["alta", "media", "baixa"]


class AnaliseOrcamento(BaseModel):
    resumo: str
    riscos: list[RiscoIA]


def montar_payload(ctx, motivos_referencia):
    """Contexto do detalhe -> texto JSON para o modelo. Sem nome de paciente."""
    orc = ctx["orcamento"]
    itens = sorted(ctx["comparacao"], key=lambda i: (i["tipo"] == "igual", -abs(i["dif_valor"]), -i["faturado"]))
    dados = {
        "orcamento": {
            "id": orc["id_orcamento"], "paciente_codigo": ctx["paciente_codigo"], "unidade": orc["unidade"],
            "operadora": orc["operadora"], "inicio": str(orc["inicio"])[:10], "fim": str(orc["fim"])[:10],
            "situacao": orc["situacao"], "tem_senha": bool((orc.get("senha") or "").strip()),
            "validade_senha": str(orc["validade_senha"])[:10] if orc.get("validade_senha") else None,
            "orcado": float(orc["orcado"] or 0), "faturado": float(orc["faturado"] or 0),
            "contas_abertas": int(orc.get("contas_abertas") or 0),
        },
        "itens": [{k: (float(v) if isinstance(v, (int, float)) or hasattr(v, "quantize") else v)
                   for k, v in i.items() if k in ("recurso", "categoria", "qtd_orcada", "qtd_faturada",
                                                  "preco_orcado", "preco_faturado", "orcado", "faturado", "tipo")}
                  for i in itens[:MAX_ITENS]],
        "riscos_regras": [r["texto"] for r in ctx["riscos"]],
        "historico_operadora": [{"motivo": h["motivo"], "descricao": h.get("descricao"), "linhas": int(h["linhas"]),
                                 "glosa": float(h["glosa"]), "recuperado": float(h["recuperado"]),
                                 "perda": float(h["perda"])} for h in ctx["historico_operadora"]],
        "glosas_deste_orcamento": [{"motivo": g["motivo"], "descricao": g.get("descricao"),
                                    "glosa": float(g["glosa"] or 0), "status": g.get("status_glosa")}
                                   for g in ctx["glosas"]],
        "motivos_tiss_referencia": motivos_referencia,
    }
    return json.dumps(dados, ensure_ascii=False, default=str)


def conferir(analise, payload_dict, codigos_tiss):
    """Recusa item ou motivo que não estão no que foi enviado. Devolve a análise."""
    recursos = {(i["recurso"] or "").strip().upper() for i in payload_dict["itens"]}
    for r in analise.riscos:
        if r.item.strip() and r.item.strip().upper() not in recursos:
            raise ia.GeracaoFalhou("A IA citou um item que não está no orçamento nem na fatura",
                                   f"Item: {r.item[:80]}")
        if r.motivo_tiss.strip() and r.motivo_tiss.strip() not in codigos_tiss:
            raise ia.GeracaoFalhou("A IA usou um código TISS que não existe na Tabela 38",
                                   f"Código: {r.motivo_tiss[:10]}")
    analise.riscos = analise.riscos[:MAX_RISCOS]
    return analise


def _referencia(ctx):
    """Motivos TISS para o modelo: os do histórico da operadora e das glosas deste orçamento."""
    codigos = {h["motivo"] for h in ctx["historico_operadora"] if h.get("motivo")} | \
              {g["motivo"] for g in ctx["glosas"] if g.get("motivo")}
    linhas = banco.consultar("SELECT codigo, descricao FROM conciliacao.motivo_tiss WHERE codigo = ANY(%s)",
                             (sorted(codigos),), "motivos TISS de referência") if codigos else []
    todos = {l["codigo"] for l in banco.consultar("SELECT codigo FROM conciliacao.motivo_tiss", (), "códigos TISS")}
    return [{"codigo": l["codigo"], "descricao": l["descricao"]} for l in linhas], todos


def ultima(id_orcamento):
    return banco.um(
        "SELECT criado_em, autor, provedor, modelo, resultado, tokens_entrada, tokens_saida, payload_hash "
        "FROM conciliacao.analise_orcamento WHERE id_orcamento = %s ORDER BY criado_em DESC LIMIT 1",
        (id_orcamento,), "última análise do orçamento")


def analisar(ctx, autor=None, forcar=False, par=None):
    """Roda (ou reaproveita) a análise do orçamento do contexto. Devolve (registro, reaproveitada)."""
    banco.garantir_schema()
    referencia, codigos = _referencia(ctx)
    payload = montar_payload(ctx, referencia)
    hash_ = hashlib.sha256(payload.encode()).hexdigest()
    anterior = ultima(ctx["orcamento"]["id_orcamento"])
    if anterior and anterior["payload_hash"] == hash_ and not forcar:
        return anterior, True

    prov = provedores.escolher(par)
    analise, truncou, entrada, saida = ia._chamar_com_retentativa(
        prov, payload, len(ctx["comparacao"]), instrucoes=INSTRUCOES, modelo=AnaliseOrcamento,
        esquema_nome="analise_orcamento")
    if truncou:
        raise ia.GeracaoFalhou(f"'{prov.slug}' truncou a resposta", "Tente um modelo sem raciocínio estendido.")
    analise = conferir(analise, json.loads(payload), codigos)
    resultado = analise.model_dump()
    with banco.conexao() as con:
        con.execute(
            "INSERT INTO conciliacao.analise_orcamento (id_orcamento, autor, provedor, modelo, payload_hash, payload, "
            "resultado, tokens_entrada, tokens_saida) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (ctx["orcamento"]["id_orcamento"], autor, prov.slug, prov.modelo, hash_, payload,
             json.dumps(resultado, ensure_ascii=False), entrada, saida))
    logger.info("orcamento_ia: orçamento %s analisado por %s (%s riscos)",
                ctx["orcamento"]["id_orcamento"], prov.rotulo, len(analise.riscos))
    return ultima(ctx["orcamento"]["id_orcamento"]), False
