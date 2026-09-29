"""Desfecho dos principais motivos: recuperado, perdido e em aberto."""

from . import comum, gm_comum

TITULO = "Desfecho dos principais motivos"
ICONE = "scale"
PARTIAL = "reports/bloco_gm_desfecho.html"
LARGURA = "inteira"
TOP = 12
ITENS = [
    {"chave": "desfecho", "titulo": "Desfecho",
     "negocio": "Barra inteira = glosa do motivo. Verde voltou pago, magenta se perdeu, âmbar ainda pode voltar. "
     "Motivo com muita perda e pouco recurso é candidato a ação na origem (cadastro, contrato, faturamento).",
     "tecnico": "Mesmas regras do ranking; os 12 maiores motivos em valor de glosa."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_motivo"))


def montar(linhas):
    topo = gm_comum.motivos(linhas)[:TOP]
    rotulos = [gm_comum.rotulo(m["motivo"], m.get("descricao")) for m in topo]
    return {
        "vazio": not topo,
        "grafico": comum.grafico("barras-h", rotulos, [
            {"nome": "Recuperado", "tom": "teal", "valores": [m["recuperado_bruto"] for m in topo]},
            {"nome": "Perda", "tom": "magenta", "valores": [m["perda"] for m in topo]},
            {"nome": "Em aberto", "tom": "amber", "valores": [m["em_aberto"] for m in topo]},
        ], empilhado=True),
        "altura": max(260, 34 * len(topo) + 60),
    }


def montar_amostra():
    return montar(gm_comum.amostra_motivos())
