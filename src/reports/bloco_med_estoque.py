"""Medicamentos: o que está parado nas farmácias e para quantos dias dá."""

import datetime

from . import comum, med_comum

TITULO = "Estoque nas farmácias"
ICONE = "warehouse"
PARTIAL = "reports/bloco_med_estoque.html"
LARGURA = "inteira"
TOP_ITENS = 25
ITENS = [
    {"chave": "valor", "titulo": "Valor em estoque",
     "negocio": "Saldo das farmácias e centros de dispensação, valorizado a custo, na última posição gravada "
     "pelo ERP antes do fim do período.",
     "tecnico": med_comum.REGRA_ESTOQUE},
    {"chave": "cobertura", "titulo": "Cobertura (dias)",
     "negocio": "Para quantos dias o estoque dá, no ritmo de consumo do período. Muito alto = capital parado ou "
     "item encalhado; muito baixo = risco de ruptura.",
     "tecnico": "Por área: valor em estoque ÷ (custo dispensado da área ÷ dias do período). Por item: saldo ÷ "
     "(quantidade líquida dispensada ÷ dias). Sem consumo no período, fica vazio. Área do consumo = "
     "MATMATERIALMOV.IDDISPENSINGAREA."},
]


def consultar(filtros):
    return montar(filtros.rodar("med_estoque_areas"), filtros.rodar("med_estoque_itens", limite=TOP_ITENS),
                  filtros.rodar("med_por_area"), filtros.rodar("med_por_item"), filtros)


def montar(areas, itens, consumo_area, consumo_item, filtros=None):
    n_dias = med_comum.dias(filtros)
    gasto_area = {l["grupo"]: comum.num(l.get("custo")) for l in consumo_area}
    qtd_item = {l["grupo"]: comum.num(l.get("quantidade")) for l in consumo_item}
    linhas_area = comum.ordenar([{**l, "valor": comum.num(l.get("valor"))} for l in areas], "valor")
    total = comum.com_participacao(linhas_area, "valor")
    for l in linhas_area:
        l["consumo"] = gasto_area.get(l["area"], 0.0)
        l["cobertura"] = med_comum.cobertura(l["valor"], l["consumo"], n_dias)
    linhas_item = []
    for l in itens:
        consumo = qtd_item.get(l["item"], 0.0)
        linhas_item.append({**l, "valor": comum.num(l.get("valor")), "consumo": consumo,
                            "cobertura": med_comum.cobertura(l.get("saldo"), consumo, n_dias)})
    data = med_comum.posicao(areas)
    top = linhas_area[:12]
    return {
        "vazio": not areas,
        "areas": linhas_area,
        "itens": linhas_item,
        "total": total,
        "dias": n_dias,
        "posicao": data,
        "velho": med_comum.estoque_velho(data, filtros),
        "com_tipo": bool(filtros and filtros.tipo),
        "parados": sum(1 for l in linhas_item if not l["consumo"]),
        "grafico": comum.grafico("barras-h", [l["area"] for l in top],
                                 [{"nome": "Em estoque", "tom": "navy", "valores": [l["valor"] for l in top]}],
                                 gradiente=True) if top else None,
    }


POSICAO = datetime.date(2026, 8, 31)
AMOSTRA_AREAS = [
    {"area": a, "unidade": u, "posicao": POSICAO, "itens": n, "valor": v}
    for a, u, n, v in [
        ("CD Pleno DF", "PLENO DF HC", 1_515, 980_000), ("CD Premier Brooklin", "Premier Brooklin HSP", 1_624, 720_000),
        ("CD Pleno SP", "PLENO SP HC", 1_381, 610_000), ("CD Pleno RJ", "PLENO RJ HC", 1_708, 540_000),
        ("CD Premier Barra", "Premier Barra HSP", 802, 410_000),
    ]
]
AMOSTRA_CONSUMO_AREA = [{"grupo": "CD Pleno DF", "custo": 742_477}, {"grupo": "CD Premier Brooklin", "custo": 434_180},
                        {"grupo": "CD Pleno SP", "custo": 170_526}, {"grupo": "CD Pleno RJ", "custo": 315_885},
                        {"grupo": "CD Premier Barra", "custo": 190_321}]
AMOSTRA_ITENS = [
    {"item": i, "categoria": "Medicamentos", "posicao": POSICAO, "saldo": s, "valor": v}
    for i, s, v in [("Imunoglobulina Humana 5g FR 50mL", 60, 98_700), ("Daptomicina 500mg FA", 310, 48_300),
                    ("Ertapenem 1g FA", 420, 69_500), ("Isavuconazonio 100mg CAP - Marca", 140, 66_200)]
]
AMOSTRA_CONSUMO_ITEM = [{"grupo": "Imunoglobulina Humana 5g FR 50mL", "quantidade": 24},
                        {"grupo": "Daptomicina 500mg FA", "quantidade": 146},
                        {"grupo": "Ertapenem 1g FA", "quantidade": 133}]


def montar_amostra():
    return montar(AMOSTRA_AREAS, AMOSTRA_ITENS, AMOSTRA_CONSUMO_AREA, AMOSTRA_CONSUMO_ITEM, comum.Filtros("2026-08"))
