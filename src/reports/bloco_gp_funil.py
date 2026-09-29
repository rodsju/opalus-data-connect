"""Onde a glosa está no ciclo: análise Opalus → operadora → pago, acatado ou mantido."""

from . import comum, gp_comum

TITULO = "Status da glosa"
ICONE = "funnel"
PARTIAL = "reports/bloco_gp_funil.html"
LARGURA = "meia"
ITENS = [
    {"chave": "status", "titulo": "Status da glosa",
     "negocio": "Em que etapa cada glosa está. Acatado e mantido são perda; pago é recuperação.",
     "tecnico": "STATUS DA GLOSA recalculado com a SWITCH da planilha (regras.status_glosa), na ordem: "
     "análise Opalus > pago > acatado/análise operadora > acatado > análise operadora > mantida."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_status"))


def montar(linhas):
    por_status = {l["status_glosa"]: l for l in gp_comum.normalizar(linhas)}
    ordem = [s for s, _, _ in gp_comum.STATUS] + sorted(set(por_status) - set(gp_comum.TOM_STATUS))
    etapas = []
    total = sum(l["glosa"] for l in por_status.values())
    for status in ordem:
        l = por_status.get(status)
        if not l:
            continue
        descricao = next((d for s, _, d in gp_comum.STATUS if s == status), "")
        etapas.append({**l, "status": status, "tom": gp_comum.TOM_STATUS.get(status, "neutral"),
                       "descricao": descricao, "pct": comum.pct(l["glosa"], total)})
    return {
        "vazio": not etapas,
        "etapas": etapas,
        "total": {"glosa": total, "linhas": sum(e["linhas"] for e in etapas)},
        "grafico": comum.grafico("rosca", [e["status"] for e in etapas],
                                 [{"nome": "Glosa", "tons": [e["tom"] for e in etapas],
                                   "valores": [e["glosa"] for e in etapas]}]),
    }


def montar_amostra():
    return montar([
        {"status_glosa": s, **gp_comum.amostra_somas(n, g * 5, g, 0, 0, 0, 0)}
        for s, n, g in [("ANÁLISE OPALUS", 94, 462_894), ("ANÁLISE OPERADORA", 1265, 4_310_000),
                        ("ACATADO / ANÁLISE OPERADORA", 180, 610_000), ("ACATADO", 2074, 994_598),
                        ("PAGO", 1257, 3_600_000), ("GLOSA MANTIDA", 235, 763_220)]
    ])
