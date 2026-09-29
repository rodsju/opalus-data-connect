"""KPIs da glosa controlada na planilha."""

from . import comum, gp_comum

TITULO = "Resumo da glosa"
ICONE = "sparkles"
PARTIAL = "reports/bloco_resumo.html"
LARGURA = "faixa"
ITENS = [
    gp_comum.ITEM_FONTE,
    {"chave": "faturado", "titulo": "Faturado (Oracle)",
     "negocio": "O faturado vem do ERP, pela conta casada com cada linha. O VALOR FATURADO da planilha serve só "
     "para conferir: quando os dois batem, a linha está conciliada.",
     "tecnico": "SUM(UNITPRICE × (QUANTITY − COVERAGEQUANTITY)) da admissão casada (conciliacao.cruzamento), "
     "uma vez por admissão."},
    {"chave": "recuperacao", "titulo": "Recuperação",
     "negocio": "Quanto do valor recursado voltou pago pela operadora.",
     "tecnico": "SUM(VALOR RECURSO RECEBIDO (BRUTO)) ÷ SUM(VALOR RECURSADO)."},
    {"chave": "perda", "titulo": "Perda",
     "negocio": "Glosa que não volta: acatada pela Opalus + mantida pela operadora.",
     "tecnico": "SUM(GLOSA ACATADA) + SUM(GLOSA MANTIDA)."},
]


def consultar(filtros):
    linhas = filtros.rodar("gp_totais")
    return montar(linhas[0] if linhas else None)


def montar(t):
    if not t:
        return {"vazio": True, "cards": []}
    t = gp_comum.normalizar([t])[0]
    perda = t["acatada"] + t["mantida"]
    return {
        "vazio": not t["linhas"],
        "cards": [
            {"rotulo": "Glosa", "valor": t["glosa"], "formato": "moeda_curta", "icone": "shield-x", "tom": "coral",
             "hint": f"{int(t['linhas'])} linhas · {_curta(comum.num(t.get('glosa_xml')))} (xml) · "
                     f"{_curta(t['glosa'] - comum.num(t.get('glosa_xml')))} (planilha)"},
            {"rotulo": "Faturado (Oracle)", "valor": t["faturado"], "formato": "moeda_curta", "icone": "database",
             "tom": "blue", "barra": comum.pct(comum.num(t.get("conciliadas")), t["linhas"]),
             "hint": f"linhas conciliadas · planilha {_curta(comum.num(t.get('faturado_planilha')))}"},
            {"rotulo": "Taxa de glosa", "valor": t["taxa_glosa"], "formato": "pct", "icone": "percent",
             "tom": "violet", "hint": "glosa ÷ faturado Oracle das linhas glosadas"},
            {"rotulo": "Recursado", "valor": t["recursado"], "formato": "moeda_curta", "icone": "send",
             "tom": "blue", "barra": comum.pct(t["recursado"], t["glosa"]), "hint": "da glosa foi recorrida"},
            {"rotulo": "Recuperado", "valor": t["recuperado_bruto"], "formato": "moeda_curta", "icone": "rotate-ccw",
             "tom": "teal", "barra": t["taxa_recuperacao"],
             "hint": f"do recursado · líquido {_curta(t['recuperado'])}"},
            {"rotulo": "Perda", "valor": perda, "formato": "moeda_curta", "icone": "trending-down", "tom": "magenta",
             "barra": comum.pct(perda, t["glosa"]),
             "hint": f"da glosa · acatada {_curta(t['acatada'])} + mantida {_curta(t['mantida'])}"},
            {"rotulo": "Sem recurso", "valor": comum.num(t.get("glosa_sem_recurso")), "formato": "moeda_curta",
             "icone": "hourglass", "tom": "amber",
             "hint": f"{int(comum.num(t.get('sem_recurso')))} glosas em análise Opalus · "
                     f"{_curta(comum.num(t.get('glosa_prazo_vencido')))} com prazo vencido"},
        ],
    }


def _curta(v):
    from .. import layout

    return layout.fmt_moeda_curta(v)


AMOSTRA = {"linhas": 5126, "faturado": 46_100_000, "faturado_planilha": 47_409_814, "conciliadas": 4875, "glosa": 10_802_168, "recursado": 9_018_664,
           "acatada": 1_301_550, "recuperado_bruto": 4_082_639, "recuperado": 3_890_389, "mantida": 763_220,
           "sem_recurso": 94, "glosa_sem_recurso": 462_894, "glosa_prazo_vencido": 1_790}


def montar_amostra():
    return montar(AMOSTRA)
