"""Risco de glosa de um orçamento, por regras -- sem IA e sem custo.

Cada regra devolve {regra, severidade, texto}: a tela mostra por que disparou.
As regras da lista usam só o que a lista já traz; as de item (desvio orçado ×
faturado) só existem no detalhe.
"""

import datetime

from . import comum

ALTA, MEDIA, BAIXA = "alta", "media", "baixa"
PESO = {ALTA: 3, MEDIA: 2, BAIXA: 1}
# Glosa ÷ fatura da operadora em 12 meses; a média do grupo fica perto de 3%.
TAXA_ALTA, TAXA_MEDIA = 6.0, 3.0


def _data(valor):
    return valor.date() if isinstance(valor, datetime.datetime) else valor


def avaliar(orc, taxas_operadora=None, pacientes_glosados=None, hoje=None):
    """Regras que valem com o que a linha da lista traz."""
    hoje = hoje or datetime.date.today()
    riscos = []
    autorizado = (orc.get("situacao") or "").startswith("Autorizado")
    validade, fim = _data(orc.get("validade_senha")), _data(orc.get("fim"))
    aberto = comum.num(orc.get("contas_abertas")) > 0 or not comum.num(orc.get("contas"))

    if autorizado and not (orc.get("senha") or "").strip():
        riscos.append({"regra": "sem_senha", "severidade": ALTA,
                       "texto": "Autorizado sem senha registrada: operadora costuma glosar por falta de senha."})
    if validade and fim and validade < fim:
        riscos.append({"regra": "senha_vence_antes", "severidade": ALTA,
                       "texto": f"Senha vale até {validade:%d/%m/%Y}, antes do fim do período ({fim:%d/%m/%Y})."})
    elif validade and aberto and validade < hoje:
        riscos.append({"regra": "senha_vencida", "severidade": ALTA,
                       "texto": f"Senha vencida em {validade:%d/%m/%Y} com conta ainda em aberto."})

    orcado, faturado = comum.num(orc.get("orcado")), comum.num(orc.get("faturado"))
    if faturado > orcado + 1:
        # Médio, não alto: o total faturado contra o orçamento costuma passar do
        # orçado (jun/2026: R$ 31,9 mi × R$ 19,6 mi) por motivo ainda não explicado;
        # o desvio que importa é o de item, avaliado no detalhe.
        riscos.append({"regra": "faturado_acima", "severidade": MEDIA,
                       "texto": f"Faturado {_moeda(faturado)} acima do orçado {_moeda(orcado)} "
                                f"({comum.pct(faturado - orcado, orcado) or 0:.0f}% a mais)."})
    if comum.num(orc.get("itens")) and not orcado:
        riscos.append({"regra": "orcado_zero", "severidade": BAIXA,
                       "texto": "Itens do orçamento sem valor: difícil conferir a fatura."})

    taxa = (taxas_operadora or {}).get(orc.get("operadora"))
    if taxa and taxa.get("taxa") is not None and taxa["taxa"] >= TAXA_MEDIA:
        riscos.append({"regra": "operadora_glosa", "severidade": ALTA if taxa["taxa"] >= TAXA_ALTA else MEDIA,
                       "texto": f"Operadora glosou {taxa['taxa']:.1f}% da fatura nos últimos 12 meses"
                                + (f" (motivo mais comum {taxa['motivo']})." if taxa.get("motivo") else ".")})
    if orc.get("id_paciente") in (pacientes_glosados or set()):
        riscos.append({"regra": "paciente_glosado", "severidade": MEDIA,
                       "texto": "Paciente já teve glosa em outras contas."})
    return riscos


def avaliar_itens(comparacao):
    """Regras do detalhe: desvios item a item entre orçado e faturado."""
    riscos, soma = [], {}
    for item in comparacao:
        soma.setdefault(item["tipo"], [0, 0.0])
        soma[item["tipo"]][0] += 1
        soma[item["tipo"]][1] += abs(item["dif_valor"])
    textos = {
        "faturado sem orçar": (ALTA, "item(ns) faturado(s) sem estar no orçamento"),
        "qtd acima": (MEDIA, "item(ns) faturado(s) em quantidade acima da orçada"),
        "preço diferente": (MEDIA, "item(ns) com preço faturado diferente do orçado"),
    }
    for tipo, (sev, texto) in textos.items():
        if tipo in soma:
            n, valor = soma[tipo]
            riscos.append({"regra": tipo, "severidade": sev, "texto": f"{n} {texto} ({_moeda(valor)})."})
    return riscos


def nivel(riscos):
    if not riscos:
        return None
    return max(riscos, key=lambda r: PESO[r["severidade"]])["severidade"]


def comparar_itens(orcados, faturados):
    """Junção completa por recurso. Cada linha: orçado, faturado, diferenças e tipo de desvio."""
    por_recurso = {}
    for lado, linhas in (("orc", orcados), ("fat", faturados)):
        for l in linhas:
            atual = por_recurso.setdefault(l["recurso_id"], {"recurso_id": l["recurso_id"], "recurso": l["recurso"],
                                                             "categoria": l["categoria"]})
            atual[lado] = l
    saida = []
    for r in por_recurso.values():
        o, f = r.get("orc"), r.get("fat")
        qo, qf = comum.num(o and o["qtd"]) - comum.num(o and o["qtd_coberta"]), \
            comum.num(f and f["qtd"]) - comum.num(f and f["qtd_coberta"])
        vo, vf = comum.num(o and o["cobrado"]), comum.num(f and f["cobrado"])
        if not o:
            tipo = "faturado sem orçar" if vf else "igual"
        elif not f:
            tipo = "orçado não faturado" if vo else "igual"
        elif abs(vo - vf) <= 0.5:
            tipo = "igual"
        elif qf > qo:
            tipo = "qtd acima"
        elif qf < qo:
            tipo = "qtd abaixo"
        else:
            tipo = "preço diferente"
        saida.append({**r, "qtd_orcada": qo, "qtd_faturada": qf, "orcado": vo, "faturado": vf,
                      "dif_qtd": qf - qo, "dif_valor": vf - vo, "tipo": tipo,
                      "preco_orcado": o and o["preco"], "preco_faturado": f and f["preco"],
                      "glosa_iw": comum.num(f and f.get("glosa_iw"))})
    ordem = {"faturado sem orçar": 0, "qtd acima": 1, "preço diferente": 2, "qtd abaixo": 3,
             "orçado não faturado": 4, "igual": 5}
    return sorted(saida, key=lambda x: (ordem[x["tipo"]], -abs(x["dif_valor"]), -x["faturado"]))


def _moeda(v):
    from .. import layout

    return layout.fmt_moeda_curta(v)
