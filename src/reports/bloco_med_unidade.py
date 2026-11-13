"""Medicamentos: onde o custo se concentra (unidade e tipo de atendimento)."""

from . import comum, med_comum

TITULO = "Custo por unidade"
ICONE = "building"
PARTIAL = "reports/bloco_med_unidade.html"
LARGURA = "meia"
ITENS = [
    {"chave": "unidade", "titulo": "Unidade",
     "negocio": "Custo do que foi dispensado aos pacientes de cada unidade de negócio, e o custo por paciente.",
     "tecnico": med_comum.REGRA_RECORTE},
    {"chave": "tipo", "titulo": "Tipo de atendimento",
     "negocio": "Home care costuma ter menos dispensações e mais caras (kit do ressuprimento); o hospital de "
     "transição, muitas dispensações de dose.",
     "tecnico": "CAPADMISSION.ADMISSIONTYPE: 0 hospital de transição, 1 home care, 3 ambulatorial."},
]

TONS_TIPO = {"Hospital de transição": "blue", "Home care": "teal", "Ambulatorial": "violet"}


def consultar(filtros):
    return montar(filtros.rodar("med_por_unidade"), filtros.rodar("med_por_tipo_atendimento"))


def montar(unidades, tipos):
    unidades = comum.ordenar([{**l, "custo": comum.num(l.get("custo"))} for l in unidades], "custo")
    total = comum.com_participacao(unidades, "custo")
    for l in unidades:
        p = comum.num(l.get("pacientes"))
        l["por_paciente"] = l["custo"] / p if p else None
    tipos = comum.ordenar([{**l, "custo": comum.num(l.get("custo"))} for l in tipos], "custo")
    comum.com_participacao(tipos, "custo")
    top = unidades[:12]
    return {
        "vazio": not unidades,
        "unidades": unidades,
        "tipos": tipos,
        "total": total,
        "grafico": comum.grafico("barras-h", [l["grupo"] for l in top],
                                 [{"nome": "Custo", "tom": "violet", "valores": [l["custo"] for l in top]}],
                                 gradiente=True) if top else None,
        "grafico_tipo": comum.grafico("rosca", [l["grupo"] for l in tipos],
                                      [{"nome": "Custo", "tons": [TONS_TIPO.get(l["grupo"], "neutral") for l in tipos],
                                        "valores": [l["custo"] for l in tipos]}]) if tipos else None,
    }


AMOSTRA_UNIDADES = [
    {"grupo": g, "custo": c, "dispensacoes": d, "pacientes": p}
    for g, c, d, p in [
        ("PLENO DF HC", 747_967, 6_356, 210), ("Premier Brooklin HSP", 456_337, 67_162, 260),
        ("PLENO RJ HC", 315_885, 2_594, 120), ("Geriatrics HC", 264_500, 2_966, 95),
        ("Premier Barra HSP", 190_321, 21_557, 140), ("PLENO SP HC", 170_526, 1_073, 60),
    ]
]
AMOSTRA_TIPOS = [
    {"grupo": "Home care", "custo": 1_462_264, "dispensacoes": 15_004, "pacientes": 520},
    {"grupo": "Hospital de transição", "custo": 698_692, "dispensacoes": 113_271, "pacientes": 720},
]


def montar_amostra():
    return montar(AMOSTRA_UNIDADES, AMOSTRA_TIPOS)
