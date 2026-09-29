"""Última execução da auditoria de contas: declarado × reconhecido."""

from . import comum

TITULO = "Auditoria de contas"
ICONE = "scale"
PARTIAL = "reports/bloco_auditoria.html"
LARGURA = "inteira"
STATUS = {10: "Declarado", 20: "Reconhecido total", 30: "Reconhecido parcial"}
ITENS = [
    {
        "chave": "reconhecido",
        "titulo": "Declarado × reconhecido",
        "negocio": "Na última rodada da auditoria de cada unidade, quanto do valor declarado foi "
        "reconhecido. Não tem recorte de mês: é a foto da última execução.",
        "tecnico": "auditoria_ultima: TTMPAUDITBILLCTR preso ao MAX(TRANSKEY) por IDHOMECARE (a tabela "
        "acumula execuções). INVOICESTATUS 10 = declarado, 20 = total, 30 = parcial.",
    },
]


def consultar(filtros):
    return montar(filtros.rodar("auditoria_ultima", com_periodo=False))


def montar(linhas):
    unidades = comum.ordenar(
        comum.somar_por(linhas, "unidade", ["docs", "declarado", "reconhecido", "nao_reconhecido"]), "declarado"
    )
    for u in unidades:
        u["pct_reconhecido"] = comum.pct(u["reconhecido"], u["declarado"])
    campos = ["docs", "declarado", "reconhecido", "nao_reconhecido"]
    total = {c: sum(u[c] for u in unidades) for c in campos}
    total["pct_reconhecido"] = comum.pct(total["reconhecido"], total["declarado"])

    por_status = comum.somar_por(
        [{**l, "status": STATUS.get(int(comum.num(l.get("invoice_status"))), str(l.get("invoice_status")))}
         for l in linhas],
        "status", ["docs", "declarado"],
    )
    topo = unidades[:12]
    return {
        "vazio": not linhas,
        "cards": [
            {"rotulo": "Declarado", "valor": total["declarado"], "formato": "moeda_curta", "icone": "file-text",
             "tom": "blue", "hint": f"{int(total['docs'])} documentos"},
            {"rotulo": "Reconhecido", "valor": total["reconhecido"], "formato": "moeda_curta",
             "icone": "check-check", "tom": "teal", "barra": total["pct_reconhecido"]},
            {"rotulo": "Não reconhecido", "valor": total["nao_reconhecido"], "formato": "moeda_curta",
             "icone": "circle-alert", "tom": "coral", "barra": comum.pct(total["nao_reconhecido"], total["declarado"])},
        ],
        "grafico": comum.grafico(
            "barras",
            [u["unidade"] for u in topo],
            [
                {"nome": "Reconhecido", "tom": "teal", "valores": [u["reconhecido"] for u in topo]},
                {"nome": "Não reconhecido", "tom": "coral", "valores": [u["nao_reconhecido"] for u in topo]},
            ],
            empilhado=True,
        ),
        "unidades": unidades,
        "por_status": por_status,
        "total": total,
    }


AMOSTRA = [
    {"unidade": u, "invoice_status": st, "docs": d, "declarado": de, "reconhecido": r, "nao_reconhecido": de - r}
    for u, st, d, de, r in [
        ("Premier Brooklin", 20, 180, 14_200_000, 14_200_000),
        ("Premier Brooklin", 30, 42, 3_900_000, 3_120_000),
        ("Premier Brooklin", 10, 18, 1_100_000, 0),
        ("Geriatrics SP", 20, 131, 9_800_000, 9_800_000),
        ("Geriatrics SP", 30, 25, 2_050_000, 1_460_000),
        ("Pleno Saúde - DF", 20, 70, 5_400_000, 5_400_000),
        ("Pleno Saúde - DF", 10, 12, 690_000, 0),
    ]
]


def montar_amostra():
    return montar(AMOSTRA)
