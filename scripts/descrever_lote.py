#!/usr/bin/env python3
"""Processa um lote de IA -- descricoes ou vetores -- fora do processo do app.

Uma tabela leva 56s na mediana para descrever, entao o lote completo passa de seis
horas -- longe demais para um request ou para uma thread do uvicorn, que reinicia a
cada arquivo salvo. A pagina /setup/lote dispara este script com start_new_session,
e ele so conversa com o Postgres.

O que muda entre as duas tarefas e so o miolo de cada item (TAREFAS, abaixo): fila,
retomada, cancelamento e paralelismo servem as duas igual.

Roda tambem na mao:  make lote ARGS="--job 7"
                     make vetores ARGS="--job 8"
"""

import argparse
import logging
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import (  # noqa: E402
    catalogo,
    embeddings,
    ia,
    log as log_mod,
    lote as lote_mod,
    provedores,
)

logger = logging.getLogger("descrever_lote")


def _descrever(item, par):
    """Gera e grava a descricao. Devolve os tokens gastos."""
    objeto = catalogo.um(
        "SELECT * FROM catalogo.objeto WHERE id = %s", (item["objeto_id"],), "objeto"
    )
    descricao, meta = ia.descrever(objeto, par)
    ia.gravar(objeto, descricao, meta)
    return meta["tokens_entrada"], meta["tokens_saida"]


def _vetorizar(item, par):
    """Vetoriza a descricao da tabela e a de cada campo.

    A API de embeddings nao reporta tokens, entao o item fica sem contagem -- o
    que a tela mostra e o numero de tabelas, nao o custo.
    """
    embeddings.vetorizar_objeto(item["objeto_id"], par)
    return None, None


# O miolo de cada item, por tarefa. Mesmo estilo do ADAPTADORES de src/ia.py.
# `mascara` nao entra aqui: a unidade dela e o PACOTE de colunas, nao o item --
# ver classificar_lote() no fim do arquivo.
TAREFAS = {"descricao": _descrever, "embedding": _vetorizar}

# Falha esperada de cada tarefa: ganha mensagem curada em vez do traceback cru.
ESPERADAS = (ia.GeracaoFalhou, embeddings.EmbutirFalhou, provedores.ConfiguracaoInvalida)


def marcar_item(item_id, status, **campos):
    """Fecha o item. terminado_em entra sempre -- sem ele a falha fica sem duracao."""
    partes = ["status = %s", "terminado_em = now()"]
    valores = [status]
    for coluna, valor in campos.items():
        partes.append(f"{coluna} = %s")
        valores.append(valor)
    valores.append(item_id)
    catalogo.executar(
        f"UPDATE catalogo.lote_ia_item SET {', '.join(partes)} WHERE id = %s",
        tuple(valores),
        f"item {item_id}",
    )


def pendentes(lote_id):
    return catalogo.consultar(
        """SELECT i.id, i.objeto_id, o.nome
             FROM catalogo.lote_ia_item i JOIN catalogo.objeto o ON o.id = i.objeto_id
            WHERE i.lote_id = %s AND i.status = 'pendente'
            ORDER BY o.nome""",
        (lote_id,),
        f"pendentes do lote {lote_id}",
    )


def cancelado(lote_id):
    lote = lote_mod.buscar(lote_id)
    return not lote or lote["status"] == "cancelado"


def processar(item, par, lote_id, tarefa="descricao"):
    """Um item. Falha aqui nunca derruba o lote -- so marca a linha."""
    if cancelado(lote_id):
        return "cancelado"

    catalogo.executar(
        """UPDATE catalogo.lote_ia_item SET status = 'rodando', iniciado_em = now()
            WHERE id = %s""",
        (item["id"],),
        f"início do item {item['id']}",
    )
    try:
        entrada, saida = TAREFAS[tarefa](item, par)
    except ESPERADAS as falha:
        detalhe = f"{falha.motivo}. {getattr(falha, 'detalhe', '')}".strip()
        logger.warning("%s falhou: %s", item["nome"], detalhe)
        marcar_item(item["id"], "falhou", erro=detalhe[:2000])
        return "falhou"
    except Exception as e:  # noqa: BLE001 - um item quebrado nao pode parar o lote
        logger.error("%s falhou de forma inesperada: %s", item["nome"], e, exc_info=True)
        marcar_item(item["id"], "falhou", erro=f"{type(e).__name__}: {e}"[:2000])
        return "falhou"

    catalogo.executar(
        """UPDATE catalogo.lote_ia_item
              SET status = 'concluido', terminado_em = now(),
                  tokens_entrada = %s, tokens_saida = %s
            WHERE id = %s""",
        (entrada, saida, item["id"]),
        f"fim do item {item['id']}",
    )
    logger.info("%s concluida", item["nome"])
    return "concluido"


# --------------------------------------------------------------------------
# Tarefa mascara: a unidade e o PACOTE de colunas, nao o item
#
# As outras duas tarefas processam um item por chamada. Aqui uma chamada leva 100
# colunas, e a mediana de colunas por objeto neste catalogo e 8 -- uma chamada por
# objeto desperdicaria 4 de cada 5 chamadas com prompt quase vazio (2.461 contra
# 455). Entao o item deixa de ser a fila e vira o ESCOPO: ele diz quais objetos
# entram, e a fila de verdade e a coluna que ainda tem `sensivel IS NULL`.
#
# Isso da o retomar de graca: coluna avaliada nao volta, porque a flag deixou de
# ser nula. Nao ha estado a reconciliar depois de um Ctrl-C.
# --------------------------------------------------------------------------

SQL_COLUNAS_PENDENTES = """
SELECT c.id, c.nome, c.tipo_completo, c.descricao_ia, c.objeto_id, o.nome AS objeto
  FROM catalogo.coluna c
  JOIN catalogo.objeto o ON o.id = c.objeto_id
 WHERE c.objeto_id = ANY(%s)
   AND c.descricao_ia IS NOT NULL AND c.descricao_ia <> ''
   AND c.sensivel IS NULL
 ORDER BY c.objeto_id, c.posicao
"""


def _fechar_itens_prontos(lote_id, objeto_ids):
    """Marca concluido o item de todo objeto que ficou sem coluna por avaliar."""
    catalogo.executar(
        """UPDATE catalogo.lote_ia_item i
              SET status = 'concluido', terminado_em = now()
            WHERE i.lote_id = %s AND i.objeto_id = ANY(%s) AND i.status <> 'concluido'
              AND NOT EXISTS (SELECT 1 FROM catalogo.coluna c
                               WHERE c.objeto_id = i.objeto_id
                                 AND c.descricao_ia IS NOT NULL
                                 AND c.descricao_ia <> '' AND c.sensivel IS NULL)""",
        (lote_id, list(objeto_ids)),
        "itens concluidos do lote de mascara",
    )


def _um_pacote(pacote, par, lote_id):
    """Uma chamada. Falha marca os itens dos objetos que o pacote tocava."""
    objeto_ids = sorted({coluna["objeto_id"] for coluna in pacote})
    try:
        vereditos, meta = ia.classificar(pacote, par)
        ia.gravar_mascara(vereditos, meta)
    except ESPERADAS as falha:
        detalhe = f"{falha.motivo}. {getattr(falha, 'detalhe', '')}".strip()
        logger.warning("pacote de %s colunas falhou: %s", len(pacote), detalhe)
        _marcar_objetos(lote_id, objeto_ids, "falhou", detalhe[:2000])
        return 0
    except Exception as e:  # noqa: BLE001 - um pacote quebrado nao para o lote
        logger.warning("pacote de %s colunas falhou: %s", len(pacote), e)
        _marcar_objetos(lote_id, objeto_ids, "falhou", f"{type(e).__name__}: {e}"[:2000])
        return 0

    _fechar_itens_prontos(lote_id, objeto_ids)
    logger.info(
        "pacote de %s colunas em %s objetos: %s sensíveis",
        len(pacote), len(objeto_ids), sum(1 for v in vereditos if v.sensivel),
    )
    return len(vereditos)


def _marcar_objetos(lote_id, objeto_ids, status, erro):
    catalogo.executar(
        """UPDATE catalogo.lote_ia_item SET status = %s, erro = %s, terminado_em = now()
            WHERE lote_id = %s AND objeto_id = ANY(%s)""",
        (status, erro, lote_id, list(objeto_ids)),
        "itens do pacote",
    )


def classificar_lote(lote_id, fila, par, trabalhadores):
    """Drena as colunas dos objetos do escopo em pacotes, ate acabar."""
    objeto_ids = [item["objeto_id"] for item in fila]
    if not objeto_ids:
        return

    colunas = catalogo.consultar(
        SQL_COLUNAS_PENDENTES, (objeto_ids,), f"colunas pendentes do lote {lote_id}"
    )
    pacotes = ia.empacotar_colunas(colunas)
    logger.info(
        "lote %s: %s colunas por avaliar em %s pacotes",
        lote_id, len(colunas), len(pacotes),
    )

    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        list(executor.map(
            lambda pacote: 0 if cancelado(lote_id) else _um_pacote(pacote, par, lote_id),
            pacotes,
        ))

    # Objeto cujas colunas ja estavam todas avaliadas antes do lote nunca passa
    # por um pacote; sem esta passada final o item dele ficaria pendente para
    # sempre e o lote nunca chegaria a 100%.
    _fechar_itens_prontos(lote_id, objeto_ids)


def rodar(lote_id, paralelismo=None, retomar=False):
    lote = lote_mod.buscar(lote_id)
    if not lote:
        logger.error("lote %s nao existe", lote_id)
        return 1
    # Cancelar significa parar: retomar um lote cancelado tem que ser explicito,
    # senao qualquer nova execucao desfaria a decisao de quem cancelou.
    if lote["status"] == "cancelado" and not retomar:
        logger.info("lote %s esta cancelado; use --retomar para continuar", lote_id)
        return 0

    # Item que ficou 'rodando' de uma execucao morta volta para a fila
    catalogo.executar(
        """UPDATE catalogo.lote_ia_item SET status = 'pendente', iniciado_em = NULL
            WHERE lote_id = %s AND status = 'rodando'""",
        (lote_id,),
        "retomada dos itens presos",
    )
    catalogo.executar(
        """UPDATE catalogo.lote_ia
              SET status = 'rodando', iniciado_em = coalesce(iniciado_em, now())
            WHERE id = %s""",
        (lote_id,),
        f"início do lote {lote_id}",
    )

    fila = pendentes(lote_id)
    trabalhadores = paralelismo or lote["paralelismo"]
    par = f"{lote['provedor']}::{lote['modelo']}"
    tarefa = lote["tarefa"]
    logger.info(
        "lote %s (%s): %s pendentes, %s em paralelo, via %s",
        lote_id, tarefa, len(fila), trabalhadores, par,
    )

    if tarefa == "mascara":
        classificar_lote(lote_id, fila, par, trabalhadores)
    else:
        with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
            list(executor.map(lambda item: processar(item, par, lote_id, tarefa), fila))

    final = "cancelado" if cancelado(lote_id) else "concluido"
    catalogo.executar(
        "UPDATE catalogo.lote_ia SET status = %s, terminado_em = now() WHERE id = %s",
        (final, lote_id),
        f"fim do lote {lote_id}",
    )
    resumo = lote_mod.progresso(lote_id)
    logger.info(
        "lote %s %s: %s concluidas, %s falharam, %s pendentes",
        lote_id,
        final,
        resumo["concluido"],
        resumo["falhou"],
        resumo["pendente"],
    )
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--job", type=int, required=True, help="id do lote a processar")
    p.add_argument("--paralelismo", type=int, help="sobrepoe o gravado no lote")
    p.add_argument("--retomar", action="store_true",
                   help="continua um lote cancelado, pelos itens ainda pendentes")
    args = p.parse_args()

    log_mod.configurar()
    return rodar(args.job, args.paralelismo, args.retomar)


if __name__ == "__main__":
    sys.exit(main())
