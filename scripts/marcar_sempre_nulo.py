#!/usr/bin/env python3
"""Marca em catalogo.coluna quais campos estao SEMPRE NULOS na amostra.

Coluna que nunca traz valor e sinal forte de campo morto -- resto de feature que
nao vingou, coluna de integracao desligada, campo que o sistema so preenche em um
fluxo raro. Neste catalogo sao 35% delas.

Le so o Postgres: nao toca no Oracle, nao precisa de VPN, nao chama API nenhuma.
Roda quantas vezes quiser, e vale rodar de novo depois de reamostrar.

    python scripts/marcar_sempre_nulo.py

O QUE A FLAG NAO DIZ. E sempre nulo NA AMOSTRA, e a amostra sao as 100 linhas mais
recentes de cada tabela. Coluna abandonada ha anos aparece como sempre nula mesmo
tendo historico cheio -- o que e informacao util, mas nao e "a coluna nunca foi
usada". Tres estados, como sensivel: NULL e "nao avaliada", que nao e "tem valor".
"""

import argparse
import logging
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import catalogo, log as log_mod  # noqa: E402

# Filho do logger do pacote: log.configurar() so instala handler em "src", entao
# um logger fora dessa arvore tem a mensagem descartada em silencio.
logger = logging.getLogger("src.marcar_sempre_nulo")

# Desenrola cada linha de amostra UMA vez e agrupa. A forma importa: sondar o
# jsonb por coluna (a.dados ? c.nome), que e o caminho obvio, leva 60 segundos
# nas 107 mil linhas de amostra; assim leva 2. Nao "simplifique" de volta.
SQL_MARCAR = """
WITH valores AS (
  SELECT a.objeto_id, kv.key AS coluna,
         count(*) FILTER (WHERE kv.value <> 'null'::jsonb) AS com_valor
    FROM catalogo.amostra a, LATERAL jsonb_each(a.dados) kv
   GROUP BY a.objeto_id, kv.key
)
UPDATE catalogo.coluna c
   SET sempre_nulo = (v.com_valor = 0), sempre_nulo_em = now()
  FROM valores v
 WHERE c.objeto_id = v.objeto_id AND c.nome = v.coluna
"""

SQL_RESUMO = """
SELECT count(*) FILTER (WHERE sempre_nulo)            AS sempre_nulas,
       count(*) FILTER (WHERE sempre_nulo IS FALSE)   AS com_valor,
       count(*) FILTER (WHERE sempre_nulo IS NULL)    AS nao_avaliadas,
       count(*)                                       AS total
  FROM catalogo.coluna
"""


def marcar():
    """Devolve o resumo depois de marcar. Coluna fora da amostra fica NULL."""
    catalogo.executar(SQL_MARCAR, (), "marcacao de colunas sempre nulas")
    return catalogo.um(SQL_RESUMO, (), "resumo das colunas sempre nulas")


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    log_mod.configurar()

    resumo = marcar()
    logger.info(
        "%s colunas sempre nulas na amostra, %s com valor, %s nao avaliadas (de %s)",
        resumo["sempre_nulas"], resumo["com_valor"], resumo["nao_avaliadas"],
        resumo["total"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
