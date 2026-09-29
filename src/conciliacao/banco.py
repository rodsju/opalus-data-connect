"""Acesso ao schema `conciliacao` no Postgres (o mesmo banco do catálogo)."""

import contextlib
import logging
import pathlib
import threading

from .. import catalogo

logger = logging.getLogger(__name__)

ARQUIVO_DDL = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "conciliacao_schema.sql"
_pronto = False
_trava = threading.Lock()


def garantir_schema():
    """Aplica o DDL (idempotente) na primeira vez que o processo precisa dele."""
    global _pronto
    if _pronto:
        return
    with _trava:
        if _pronto:
            return
        with conexao() as con:
            con.execute(ARQUIVO_DDL.read_text(encoding="utf-8"))
        _pronto = True
        logger.info("schema conciliacao aplicado")


@contextlib.contextmanager
def conexao():
    """Conexão com commit na saída limpa; falha vira catalogo.ConsultaFalhou."""
    import psycopg

    try:
        with psycopg.connect(catalogo.DSN, connect_timeout=5) as con:
            yield con
    except catalogo.ConsultaFalhou:
        raise
    except Exception as falha:
        logger.error("conciliacao: falha no Postgres: %s", falha, exc_info=True)
        raise catalogo.ConsultaFalhou("conciliação", falha) from falha


def consultar(sql, params=(), descricao="conciliação"):
    garantir_schema()
    return catalogo.consultar(sql, params, descricao)


def um(sql, params=(), descricao="conciliação"):
    linhas = consultar(sql, params, descricao)
    return linhas[0] if linhas else None


def carga_ativa(tipo="glosa"):
    return um(
        "SELECT id, arquivo, criada_em, data_referencia, linhas, rejeitadas, autor, cruzada_em "
        "FROM conciliacao.carga WHERE tipo = %s AND ativa",
        (tipo,), "carga ativa",
    )


def obter_carga(carga_id):
    return um("SELECT id, arquivo, criada_em, data_referencia, linhas, ativa FROM conciliacao.carga WHERE id = %s",
              (carga_id,), f"carga {carga_id}")
