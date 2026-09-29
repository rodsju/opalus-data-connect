"""Mapa de calor convênio × motivo."""

from . import comum

TITULO = "Convênio × motivo"
ICONE = "grid-3x3"
PARTIAL = "reports/bloco_gm_convenio.html"
LARGURA = "inteira"
N_CONVENIOS, N_MOTIVOS = 10, 8
ITENS = [
    {"chave": "mapa", "titulo": "Mapa de calor",
     "negocio": "Quais operadoras glosam por quais motivos. A cor mais forte marca a combinação de maior valor.",
     "tecnico": f"gm_convenio_motivo: os {N_CONVENIOS} convênios e os {N_MOTIVOS} motivos de maior glosa no "
     "recorte; o resto some na coluna 'Demais'."},
]


def consultar(filtros):
    return montar(filtros.rodar("gm_convenio_motivo"))


def montar(linhas):
    por_conv, por_mot, celula = {}, {}, {}
    for l in linhas:
        g = comum.num(l["glosa"])
        por_conv[l["convenio"]] = por_conv.get(l["convenio"], 0) + g
        por_mot[l["motivo"]] = por_mot.get(l["motivo"], 0) + g
        celula[(l["convenio"], l["motivo"])] = celula.get((l["convenio"], l["motivo"]), 0) + g
    convenios = sorted(por_conv, key=por_conv.get, reverse=True)[:N_CONVENIOS]
    motivos = sorted(por_mot, key=por_mot.get, reverse=True)[:N_MOTIVOS]
    maior = max((celula.get((c, m), 0) for c in convenios for m in motivos), default=0)
    matriz = []
    for c in convenios:
        celulas = [{"motivo": m, "valor": celula.get((c, m), 0),
                    "intensidade": round((celula.get((c, m), 0) / maior) * 100) if maior else 0} for m in motivos]
        demais = por_conv[c] - sum(x["valor"] for x in celulas)
        matriz.append({"convenio": c, "celulas": celulas, "demais": demais, "total": por_conv[c]})
    return {"vazio": not linhas, "motivos": motivos, "matriz": matriz}


def montar_amostra():
    import itertools

    convs = ["CASSI", "BRADESCO SAUDE", "REAL GRANDEZA", "AMIL", "CAPESESP"]
    mots = ["1705", "2401", "2514", "1702", "3108"]
    valores = itertools.cycle([520_000, 80_000, 0, 140_000, 30_000, 260_000, 12_000])
    return montar([{"convenio": c, "motivo": m, "linhas": 10, "glosa": next(valores)} for c in convs for m in mots])
