"""Evolução diária da ocupação nos últimos 90 dias."""

import datetime

from . import comum, oc_comum

TITULO = "Evolução da ocupação (90 dias)"
ICONE = "chart-line"
PARTIAL = "reports/bloco_oc_evolucao.html"
LARGURA = "inteira"
ITENS = [
    {"chave": "censo", "titulo": "Censo diário",
     "negocio": "Quantos estavam em atendimento no fim de cada dia. Transição com taxa sobre os leitos de hoje; "
     "home care só o censo.",
     "tecnico": "Entrada até o dia e (alta depois do dia, ou ainda em atendimento), só STATUS 1 e 2. Reproduz o "
     "STATUS 1 de hoje. A taxa usa os leitos vigentes hoje em todo o período."},
]


def consultar(filtros):
    return montar(oc_comum.historico(filtros), oc_comum.leitos(filtros))


def montar(linhas, capacidade):
    dias = sorted({l["dia"] for l in linhas})
    ht, hc = {}, {}
    for l in linhas:
        alvo = ht if l["tipo"] == oc_comum.HT else hc if l["tipo"] == oc_comum.HC else None
        if alvo is None:
            continue
        if alvo is ht and l["unidade"] not in capacidade:
            continue  # taxa só onde há leito cadastrado
        alvo[l["dia"]] = alvo.get(l["dia"], 0) + int(comum.num(l["ocupados"]))
    total = sum(capacidade.values())
    rotulos = [(d.date() if isinstance(d, datetime.datetime) else d).strftime("%d/%m") for d in dias]
    return {
        "vazio": not linhas,
        "grafico_ht": comum.grafico("barras-linha", rotulos, [
            {"nome": "Ocupados (transição)", "tom": "teal", "valores": [ht.get(d, 0) for d in dias]},
            {"nome": "Taxa de ocupação", "tom": "coral", "tipo": "linha", "eixo": "pct",
             "valores": [comum.pct(ht.get(d, 0), total) or 0 for d in dias]},
        ], formato="int") if ht else None,
        "grafico_hc": comum.grafico("barras", rotulos, [
            {"nome": "Home care ativos", "tom": "magenta", "valores": [hc.get(d, 0) for d in dias]},
        ], formato="int") if hc else None,
    }


def montar_amostra():
    hoje = datetime.date(2026, 9, 28)
    linhas = []
    for i in range(30):
        d = hoje - datetime.timedelta(days=29 - i)
        linhas += [{"dia": d, "unidade": "Premier Brooklin HSP", "tipo": 0, "ocupados": 55 + i % 8},
                   {"dia": d, "unidade": "PLENO RJ HC", "tipo": 1, "ocupados": 1100 + i}]
    return montar(linhas, {"Premier Brooklin HSP": 90})
