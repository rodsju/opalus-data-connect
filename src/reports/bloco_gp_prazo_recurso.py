"""Glosas ainda sem recurso e o prazo para recorrer."""

from . import comum

TITULO = "Prazo de recurso"
ICONE = "alarm-clock"
PARTIAL = "reports/bloco_gp_prazo_recurso.html"
LARGURA = "inteira"
FAIXAS = [("vencido", "coral"), ("até 7 dias", "amber"), ("8 a 15 dias", "violet"), ("16 a 30 dias", "blue"),
          ("mais de 30 dias", "teal"), ("sem prazo", "neutral")]
ITENS = [
    {"chave": "prazo", "titulo": "Prazo para recorrer",
     "negocio": "Glosas em análise Opalus (sem recurso enviado), pelo tempo que falta até o prazo da operadora. "
     "Vencido = dinheiro perdido se ninguém recorrer. Clique numa faixa para ver os casos em Consultas › Glosas.",
     "tecnico": "DATA DE PRAZO P/ RECURSO = DATA RECEBIMENTO + PREMISSAS_RECURSO[CONVENIO].prazo, contra a data "
     "de referência da carga (o HOJE da planilha). 'sem prazo' = convênio sem prazo de recurso cadastrado."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_prazo_faixas"))


def montar(faixas):
    por_faixa = {f["faixa"]: f for f in faixas}
    cards = []
    for nome, tom in FAIXAS:
        f = por_faixa.get(nome, {"linhas": 0, "glosa": 0})
        cards.append({"faixa": nome, "tom": tom, "linhas": int(comum.num(f["linhas"])), "glosa": comum.num(f["glosa"])})
    return {
        "vazio": not faixas,
        "faixas": cards,
    }


def montar_amostra():
    return montar(
        [{"faixa": f, "linhas": n, "glosa": g} for f, n, g in
         [("vencido", 2, 1790), ("até 7 dias", 9, 41_000), ("8 a 15 dias", 14, 62_000),
          ("16 a 30 dias", 3, 55_063), ("mais de 30 dias", 21, 180_000), ("sem prazo", 45, 123_000)]],
    )
