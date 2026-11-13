"""Medicamentos: os que mais custam e os mais usados."""

from . import comum, med_comum

TITULO = "Mais caros e mais usados"
ICONE = "list-ordered"
PARTIAL = "reports/bloco_med_ranking.html"
LARGURA = "inteira"
TOP = 20
TOP_USO = 12
ITENS = [
    {"chave": "custo", "titulo": "Por custo",
     "negocio": "Os itens que mais pesam no custo do período, com a participação acumulada (pareto): poucos "
     "itens caros costumam explicar boa parte do total.",
     "tecnico": "Agrupado por SCCCODE.CODENAME. " + med_comum.REGRA_CUSTO},
    {"chave": "uso", "titulo": "Mais usados",
     "negocio": "Os itens que mais saíram da farmácia, pelo número de dispensações. Soro e itens baratos "
     "lideram aqui sem aparecer no ranking de custo.",
     "tecnico": "Dispensações = linhas de MOVTYPE 11/14 entregues; pacientes = IDPATIENT distintos."},
    {"chave": "unitario", "titulo": "Custo médio unitário",
     "negocio": "Custo líquido ÷ quantidade líquida, na unidade de estoque do item (ampola, frasco, comprimido).",
     "tecnico": "SUM(± QUANTITY × UNITCOST) ÷ SUM(± QUANTITY); vazio quando a quantidade líquida é zero."},
]


def consultar(filtros):
    return montar(filtros.rodar("med_por_item"), filtros)


def montar(linhas, filtros=None):
    itens = []
    for l in linhas:
        quantidade = comum.num(l.get("quantidade"))
        itens.append({**l, "item": l.get("grupo"), "custo": comum.num(l.get("custo")),
                      "unitario": comum.num(l.get("custo")) / quantidade if quantidade else None})
    itens = comum.ordenar(itens, "custo")
    total = comum.com_participacao(itens, "custo")
    top = comum.top_com_outros(itens, "item", ["custo", "quantidade", "dispensacoes"], TOP, "Demais itens")
    uso = sorted(itens, key=lambda l: comum.num(l.get("dispensacoes")), reverse=True)[:TOP_USO]
    graf_custo = itens[:10]
    todas = filtros is not None and filtros.categoria == "todas"
    return {
        "vazio": not itens,
        "itens": top,
        "total": {"custo": total, "itens": len(itens),
                  "dispensacoes": sum(comum.num(l.get("dispensacoes")) for l in itens)},
        "com_categoria": todas,
        "n_80": next((i + 1 for i, l in enumerate(itens) if (l.get("pct_acum") or 0) >= 80), len(itens)),
        "grafico_custo": comum.grafico("barras-h", [_curto(l["item"]) for l in graf_custo],
                                       [{"nome": "Custo", "tom": "violet",
                                         "valores": [l["custo"] for l in graf_custo]}], gradiente=True)
        if graf_custo else None,
        "grafico_uso": comum.grafico("barras-h", [_curto(l["item"]) for l in uso],
                                     [{"nome": "Dispensações", "tom": "blue",
                                       "valores": [l.get("dispensacoes") for l in uso]}], formato="int",
                                     gradiente=True) if uso else None,
    }


def _curto(nome, n=38):
    nome = (nome or "").strip()
    return nome if len(nome) <= n else nome[: n - 1] + "…"


AMOSTRA = [
    {"grupo": g, "categoria": "Medicamentos", "custo": c, "quantidade": q, "dispensacoes": d, "pacientes": p,
     "devolvido": 0, "sem_custo": 0}
    for g, c, q, d, p in [
        ("Ceftazidima + Avibactam (2000+500)mg FA - Marca", 42_990, 67, 20, 4),
        ("Imunoglobulina Humana 5g FR 50mL", 39_468, 24, 7, 1),
        ("Daptomicina 500mg FA", 22_773, 146, 40, 8),
        ("Ertapenem 1g FA", 22_023, 133, 18, 10),
        ("Cl. Sodio 0,9% FR 100mL", 15_913, 5_924, 1_491, 190),
        ("Cl. Sodio 0,9% AMP 10mL", 14_844, 40_486, 5_633, 379),
        ("Budesonida 0,5mg/mL FLAC 2mL - Marca", 13_476, 1_412, 197, 35),
        ("Meropenem 1g FA", 13_355, 1_174, 398, 38),
        ("Dipirona 500mg/mL AMP 2mL", 4_210, 9_870, 3_950, 410),
        ("Omeprazol 20mg CAP", 1_980, 11_200, 2_870, 260),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
