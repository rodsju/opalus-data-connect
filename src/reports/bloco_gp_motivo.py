"""Códigos de glosa (TISS) mais frequentes."""

from . import comum, gp_comum

TITULO = "Motivos (código TISS)"
ICONE = "list-ordered"
PARTIAL = "reports/bloco_gp_motivo.html"
LARGURA = "meia"
TOP = 12
ITENS = [
    {"chave": "motivo", "titulo": "Motivo",
     "negocio": "Os códigos de glosa que mais pesam em valor, com a descrição da Tabela 38 do TISS (sincronizada "
     "com a ANS em Conciliação › Premissas). 'Fora da versão vigente' = código retirado pela ANS mas ainda usado.",
     "tecnico": "gp_por_motivo: coluna MOTIVO da planilha + conciliacao.motivo_tiss; classificação mais comum "
     "de cada código."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_motivo"))


def montar(linhas):
    linhas = comum.ordenar(gp_comum.normalizar(linhas), "glosa")
    total = comum.com_participacao(linhas, "glosa")
    maior = linhas[0]["glosa"] if linhas else 0
    for l in linhas:
        l["barra"] = comum.pct(l["glosa"], maior)
    return {
        "vazio": not linhas,
        "linhas": linhas[:TOP],
        "demais": len(linhas) - TOP if len(linhas) > TOP else 0,
        "total": {"glosa": total},
    }


def montar_amostra():
    return montar([
        {"motivo": m, "descricao": d, "classificacao": c, **gp_comum.amostra_somas(n, 0, g, 0, 0, 0, 0)}
        for m, d, c, n, g in [("1705", None, "CADASTRO", 2394, 1_830_616), ("2401", None, "OPERADORA", 247, 910_000),
                              ("1749", None, "OPERADORA", 120, 640_000), ("2101", None, "CADASTRO", 131, 410_000),
                              ("2001", None, "CADASTRO", 124, 300_000)]
    ])
