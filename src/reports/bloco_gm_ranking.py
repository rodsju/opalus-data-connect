"""Todos os códigos de glosa, com o desfecho de cada um."""

from . import comum, gm_comum, gp_comum

TITULO = "Ranking dos motivos"
ICONE = "list-ordered"
PARTIAL = "reports/bloco_gm_ranking.html"
LARGURA = "inteira"
ITENS = [
    gp_comum.ITEM_FONTE,
    {"chave": "desfecho", "titulo": "Desfecho por motivo",
     "negocio": "Para cada código: quanto foi recorrido, quanto voltou pago (recuperado), quanto se perdeu "
     "(acatado pela Opalus + mantido pela operadora) e quanto ainda está em aberto. Mostra onde vale recorrer.",
     "tecnico": "Recuperado = VALOR RECURSO RECEBIDO (BRUTO); perda = GLOSA ACATADA + GLOSA MANTIDA; em aberto = "
     "glosa − recuperado − perda. Descrição: Tabela 38 do TISS sincronizada com a ANS."},
]


def consultar(filtros):
    return montar(filtros.rodar("gp_por_motivo"))


def montar(linhas):
    motivos = gm_comum.motivos(linhas)
    total = comum.com_participacao(motivos, "glosa")
    campos = ["linhas", "glosa", "recursado", "recuperado_bruto", "perda", "em_aberto"]
    soma = {c: sum(m[c] for m in motivos) for c in campos}
    return {
        "vazio": not motivos,
        "linhas": motivos,
        "total": {**soma, "glosa": total,
                  "pct_recuperado": comum.pct(soma["recuperado_bruto"], total),
                  "pct_perda": comum.pct(soma["perda"], total)},
        "sem_descricao": sum(1 for m in motivos if not m.get("descricao")),
    }


def montar_amostra():
    return montar(gm_comum.amostra_motivos())
