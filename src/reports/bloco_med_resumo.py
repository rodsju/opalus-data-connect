"""Medicamentos: custo do período, pacientes e valor parado em estoque."""

import datetime

from .. import layout
from . import comum, med_comum

TITULO = "Resumo de medicamentos"
ICONE = "pill"
PARTIAL = "reports/bloco_med_resumo.html"
LARGURA = "faixa"
ITENS = [
    {"chave": "custo", "titulo": "Custo dispensado",
     "negocio": "Quanto custou o que saiu da farmácia para o paciente no período, já descontado o que voltou. "
     "É custo de aquisição, não o preço cobrado da operadora.",
     "tecnico": med_comum.REGRA_CUSTO},
    {"chave": "pacientes", "titulo": "Pacientes e custo por paciente",
     "negocio": "Pacientes distintos que receberam algum item da categoria; o custo por paciente divide o custo "
     "líquido por eles.",
     "tecnico": "COUNT(DISTINCT CAPADMISSION.IDPATIENT) nas dispensações (11 e 14). " + med_comum.REGRA_RECORTE},
    {"chave": "estoque", "titulo": "Valor em estoque",
     "negocio": "Quanto há nas farmácias na última posição do ERP antes do fim do período.",
     "tecnico": med_comum.REGRA_ESTOQUE},
]


def consultar(filtros):
    categorias = filtros.rodar("med_por_categoria") if filtros.categoria == "todas" else []
    return montar(filtros.rodar("med_por_total"), categorias, med_comum.estoque_areas(filtros), filtros)


def montar(total, categorias, estoque, filtros=None):
    t = total[0] if total else {}
    custo = comum.num(t.get("custo"))
    pacientes = int(comum.num(t.get("pacientes")))
    dispensacoes = int(comum.num(t.get("dispensacoes")))
    sem_custo = int(comum.num(t.get("sem_custo")))
    devolvido = comum.num(t.get("devolvido"))
    n_dias = med_comum.dias(filtros)
    cards = [
        {"rotulo": "Custo dispensado", "valor": custo, "formato": "moeda_curta", "icone": "pill", "tom": "violet",
         "hint": f"{layout.fmt_moeda_curta(custo / n_dias)} por dia" if n_dias else "líquido de devoluções"},
        {"rotulo": "Dispensações", "valor": dispensacoes, "formato": "int", "icone": "package-check", "tom": "blue",
         "hint": f"{layout.fmt(sem_custo)} sem custo no ERP" if sem_custo else "todas com custo"},
        {"rotulo": "Pacientes", "valor": pacientes, "formato": "int", "icone": "users", "tom": "teal",
         "hint": f"{layout.fmt_moeda_curta(custo / pacientes)} por paciente" if pacientes else "—"},
        {"rotulo": "Devolvido", "valor": devolvido, "formato": "moeda_curta", "icone": "undo-2", "tom": "amber",
         "barra": comum.pct(devolvido, custo + devolvido), "hint": "do dispensado voltou à farmácia"},
    ]
    if estoque is not None:
        valor = sum(comum.num(l.get("valor")) for l in estoque)
        data = med_comum.posicao(estoque)
        velho = med_comum.estoque_velho(data, filtros)
        cards.append({"rotulo": "Valor em estoque", "valor": valor, "formato": "moeda_curta", "icone": "warehouse",
                      "tom": "coral" if velho else "navy",
                      "hint": (f"posição de {data:%d/%m/%Y}" + (" · desatualizada" if velho else ""))
                      if data else "sem posição no período"})
    linhas_cat = [{**l, "pct": comum.pct(l.get("custo"), custo)} for l in categorias]
    return {"vazio": not t and not estoque, "cards": cards, "categorias": linhas_cat}


AMOSTRA_TOTAL = [{"grupo": "total", "custo": 2_160_000, "quantidade": 512_000, "dispensacoes": 137_100,
                  "sem_custo": 3_400, "devolvido": 157_000, "pacientes": 1_240}]
AMOSTRA_ESTOQUE = [
    {"area": "CD Pleno DF", "unidade": "PLENO DF HC", "posicao": datetime.date(2026, 8, 31), "itens": 1_515,
     "valor": 980_000},
    {"area": "CD Premier Brooklin", "unidade": "Premier Brooklin HSP", "posicao": datetime.date(2026, 8, 31),
     "itens": 1_624, "valor": 720_000},
]


def montar_amostra():
    filtros = comum.Filtros("2026-08")
    return montar(AMOSTRA_TOTAL, [], AMOSTRA_ESTOQUE, filtros)
