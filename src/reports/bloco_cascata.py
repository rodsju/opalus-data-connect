"""Cascata da conta no mês: do bruto lançado até a fatura da operadora."""

from . import comum

TITULO = "Cascata da conta"
ICONE = "chart-column-decreasing"
PARTIAL = "reports/bloco_cascata.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "bruto", "titulo": "Bruto lançado",
     "negocio": "Tudo o que foi lançado nas contas do mês, a preço de tabela.",
     "tecnico": "SUM(UNITPRICE × QUANTITY) dos itens, fora imposto e simulação."},
    {"chave": "pacote", "titulo": "Incluso em pacote",
     "negocio": "Itens cobertos por diária/pacote: aparecem na conta mas não são cobrados à parte.",
     "tecnico": "SUM(UNITPRICE × COVERAGEQUANTITY) menos a pré-auditoria. Validado contra a planilha de glosa do "
     "financeiro: o faturado de cada admissão = bruto − coberto, ao centavo, em 95% das linhas."},
    {"chave": "pre_auditoria", "titulo": "Pré-auditoria (glosa interna)",
     "negocio": "O que a auditoria interna cortou antes de mandar a conta para a operadora.",
     "tecnico": "CAPPAYMENTITEM.PREAUDITBILL*: o corte é gravado como cobertura, então sai de dentro do coberto. "
     "UNITPRICE × LEAST(PREAUDITBILLQUANT, COVERAGEQUANTITY)."},
    {"chave": "particular", "titulo": "Particular",
     "negocio": "Cobrado do paciente: conta emitida contra a própria empresa do grupo (Premier Flamengo, "
     "Geriatrics - Part...).",
     "tecnico": "Conta cuja entidade (CAPPAYMENT.IDENTERPRISE) tem GLBENTERPRISE.CORPORATION=1. PAYERTYPE=3 não serve: "
     "também marca contas de operadora."},
    {"chave": "fatura", "titulo": "Fatura operadora",
     "negocio": "O que vai na nota para a operadora e vira contas a receber.",
     "tecnico": "Faturamento do grupo − particular."},
    {"chave": "tributos", "titulo": "Tributos da conta (ERP)",
     "negocio": "IR, PIS, COFINS, ISS e CSLL lançados na conta (~8,7%). Não é a retenção da operadora, que varia "
     "por convênio (ver Glosa (xml/planilha)).",
     "tecnico": "SUM(UNITCOST × QUANTITY) dos itens RESOURCETYPE 15."},
]


def consultar(filtros):
    return montar(filtros.rodar("cascata_por_pagador"))


def montar(linhas):
    t = {c: sum(comum.num(l.get(c)) for l in linhas)
         for c in ("bruto", "pacote", "pre_auditoria", "faturamento_grupo", "particular", "fatura_operadora",
                   "tributos_erp")}
    dados = comum.cascata([
        ("Bruto lançado", t["bruto"], "total", "tudo lançado, a preço de tabela"),
        ("Incluso em pacote", t["pacote"], "neg", "coberto por diária/pacote, não cobrado"),
        ("Pré-auditoria", t["pre_auditoria"], "neg", "glosa interna: cortado antes do envio"),
        ("Faturamento do grupo", t["faturamento_grupo"], "total", "o que foi cobrado"),
        ("Particular", t["particular"], "neg", "cobrado do paciente"),
        ("Fatura operadora", t["fatura_operadora"], "total", "vai na NF, gera contas a receber"),
    ])
    # A cascata tem de fechar: diferença acima de R$ 1 é bug de regra, não arredondamento.
    dados["fecha"] = (abs(t["bruto"] - t["pacote"] - t["pre_auditoria"] - t["faturamento_grupo"]) <= 1
                      and abs(t["faturamento_grupo"] - t["particular"] - t["fatura_operadora"]) <= 1)
    dados["tributos"] = t["tributos_erp"]
    dados["tributos_pct"] = comum.pct(t["tributos_erp"], t["faturamento_grupo"])
    dados["vazio"] = not t["bruto"]
    return dados


def montar_amostra():
    return montar([
        {"grupo": "operadora", "bruto": 29_900_000, "pacote": 11_950_000, "pre_auditoria": 50_000,
         "faturamento_grupo": 17_900_000,
         "particular": 0, "fatura_operadora": 17_900_000, "tributos_erp": 1_560_000},
        {"grupo": "particular", "bruto": 1_140_000, "pacote": 400_000, "faturamento_grupo": 740_000,
         "particular": 740_000, "fatura_operadora": 0, "tributos_erp": 45_000},
    ])

