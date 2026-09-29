"""Os principais motivos mês a mês."""

import datetime

from . import comum, gp_comum

TITULO = "Motivos por competência"
ICONE = "chart-column"
PARTIAL = "reports/bloco_gm_evolucao.html"
LARGURA = "inteira"
TOP = 5
TONS = ["coral", "blue", "violet", "amber", "teal"]
ITENS = [
    {"chave": "evolucao", "titulo": "Evolução",
     "negocio": "Glosa dos 5 maiores motivos por competência; o resto em 'Demais'. Mostra se um motivo está "
     "crescendo depois de uma mudança de contrato ou de processo.",
     "tecnico": "gm_evolucao, sem o filtro de período (mostra todas as competências do recorte)."},
]


def consultar(filtros):
    return montar(filtros.rodar("gm_evolucao", com_periodo=False))


def montar(linhas):
    total = {}
    for l in linhas:
        total[l["motivo"]] = total.get(l["motivo"], 0) + comum.num(l["glosa"])
    topo = sorted(total, key=total.get, reverse=True)[:TOP]
    competencias = sorted({l["competencia"] for l in linhas})
    valor = {}
    for l in linhas:
        chave = l["motivo"] if l["motivo"] in topo else "Demais"
        valor[(l["competencia"], chave)] = valor.get((l["competencia"], chave), 0) + comum.num(l["glosa"])
    series = [{"nome": m, "tom": TONS[i], "valores": [valor.get((c, m), 0) for c in competencias]}
              for i, m in enumerate(topo)]
    if any(k[1] == "Demais" for k in valor):
        series.append({"nome": "Demais", "tom": "neutral", "valores": [valor.get((c, "Demais"), 0) for c in competencias]})
    return {
        "vazio": not linhas,
        "grafico": comum.grafico("barras", [gp_comum.competencia_rotulo(c) for c in competencias], series,
                                 empilhado=True),
    }


def montar_amostra():
    linhas = []
    for i in range(8):
        comp = datetime.date(2025, 10 + i, 1) if i < 3 else datetime.date(2026, i - 2, 1)
        for m, base in (("1705", 180_000), ("2401", 70_000), ("2514", 60_000), ("1702", 50_000), ("0000", 30_000)):
            linhas.append({"competencia": comp, "motivo": m, "glosa": base * (1 + (i % 3) * 0.2)})
    return montar(linhas)
