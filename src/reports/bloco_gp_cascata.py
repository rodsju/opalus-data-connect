"""Cascata da glosa: da fatura da operadora (Oracle) até o saldo a receber (planilha)."""

from . import comum, gp_comum

TITULO = "Da fatura ao saldo a receber"
ICONE = "chart-column-decreasing"
PARTIAL = "reports/bloco_gp_cascata.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "fatura", "titulo": "Fatura operadora (Oracle)",
     "negocio": "Faturado das admissões que tiveram glosa, calculado no ERP. Só entram linhas da planilha casadas "
     "com a conta do ERP.",
     "tecnico": "conciliacao.cruzamento.faturado_erp = SUM(preço × (qtd − qtd coberta)) da admissão, uma vez por "
     "admissão."},
    {"chave": "retencao", "titulo": "Retenção da operadora",
     "negocio": "Imposto retido pela operadora na fonte; varia por convênio (0% a ~9,5%).",
     "tecnico": "Fatura × alíquota da tabela de parâmetros de imposto (Conciliação › Premissas), por empresa + "
     "convênio fórmula."},
    {"chave": "recebido", "titulo": "Recebido e recurso",
     "negocio": "O que entrou na conta corrente pela fatura e, depois, pelo recurso de glosa.",
     "tecnico": "VALOR RECEBIDO C/C e VALOR RECURSO RECEBIDO (LIQUIDO) da planilha."},
    {"chave": "perda", "titulo": "Perda e saldo",
     "negocio": "Perda = glosa acatada pela Opalus + mantida pela operadora. O saldo é o que ainda pode entrar: "
     "glosa em análise e diferenças de recebimento.",
     "tecnico": "(GLOSA ACATADA + GLOSA MANTIDA) × (1 − retenção); saldo = líquido − recebido − recurso − perda."},
]


def consultar(filtros):
    linhas = filtros.rodar("gp_cascata")
    return montar(linhas[0] if linhas else None)


def montar(t):
    if not t or not comum.num(t.get("fatura")):
        return {"vazio": True}
    v = {k: comum.num(t.get(k)) for k in ("fatura", "retencao", "recebido", "recurso", "perda", "faturado_sem_erp")}
    liquido = v["fatura"] - v["retencao"]
    saldo = liquido - v["recebido"] - v["recurso"] - v["perda"]
    dados = comum.cascata([
        ("Fatura operadora", v["fatura"], "total", "calculada no ERP (Oracle)"),
        ("Retenção", v["retencao"], "neg", "imposto retido pela operadora (premissa)"),
        ("Líquido previsto", liquido, "total", "o que deveria entrar"),
        ("Recebido na conta", v["recebido"], "saida", "planilha: valor recebido C/C"),
        ("Recurso recebido", v["recurso"], "saida", "planilha: recurso recebido líquido"),
        ("Perda", v["perda"], "neg", "glosa acatada + mantida"),
        ("Saldo a receber", saldo, "total", "glosa em análise e diferenças"),
    ])
    dados.update({"vazio": False, "sem_erp": int(comum.num(t.get("sem_erp"))),
                  "faturado_sem_erp": v["faturado_sem_erp"], "linhas": int(comum.num(t.get("linhas")))})
    return dados


def montar_amostra():
    return montar({"linhas": 5126, "sem_erp": 251, "faturado_sem_erp": 1_450_000, "fatura": 45_950_000,
                   "retencao": 2_900_000, "recebido": 33_100_000, "recurso": 3_890_000, "perda": 1_950_000})


ITENS.insert(0, gp_comum.ITEM_FONTE)
