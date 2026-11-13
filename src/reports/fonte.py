"""Porta única de dados dos /reports.

Os blocos chamam rodar("contas_por_status", params) e recebem list[dict] com
chaves em minúsculo. Qual banco responde é decidido aqui, por REPORTS_FONTE:
"bq" (default, camada bronze do BigQuery -- ver fonte_bq) e "oracle" (legado).
Trocar de origem não toca em bloco nem template -- só num sql_<fonte>.py com as mesmas chaves.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)


class ConsultaFalhou(Exception):
    """A consulta não voltou. `motivo` é curto; `dica` diz o que fazer."""

    def __init__(self, nome, motivo, dica=""):
        super().__init__(f"{nome}: {motivo}")
        self.nome = nome
        self.motivo = motivo
        self.dica = dica
        # Sem conexão, todos os blocos vão falhar igual: a página mostra um
        # alerta só, em vez de doze "item indisponível" sem explicação.
        self.sem_conexao = False


def _backend():
    fonte = (os.getenv("REPORTS_FONTE") or "bq").strip().lower()
    if fonte == "bq":
        from . import fonte_bq

        return fonte_bq
    if fonte == "oracle":
        from . import fonte_oracle

        return fonte_oracle
    raise ConsultaFalhou("fonte", f"REPORTS_FONTE='{fonte}' não suportada", "use 'bq' ou 'oracle'")


def rodar(nome, params, limite=None):
    # Consultas da Conciliação (carga da planilha) moram no Postgres, qualquer
    # que seja a fonte do ERP.
    from . import sql_pg

    if nome in sql_pg.CONSULTAS:
        from . import fonte_pg as backend
    else:
        backend = _backend()
    return _medir(nome, lambda: backend.rodar(nome, params, limite=limite))


def formulario(tabela, ids):
    """Linhas do formulário de evolução `tabela` (TD*) para as evoluções `ids`."""
    backend = _backend()
    return _medir(f"formulario {tabela}", lambda: backend.rodar_formulario(tabela, ids))


def _medir(nome, chamada):
    inicio = time.perf_counter()
    try:
        linhas = chamada()
    except Exception as erro:
        indisponivel = type(erro).__name__ in ("OracleIndisponivel", "BqIndisponivel")
        falha = ConsultaFalhou(
            nome,
            getattr(erro, "motivo", None) or str(erro).strip().splitlines()[0],
            getattr(erro, "dica", ""),
        )
        falha.sem_conexao = indisponivel
        logger.error("reports: %s falhou: %s", nome, erro)
        raise falha from erro
    logger.info(
        "reports: %s -> %d linhas em %.0f ms", nome, len(linhas), (time.perf_counter() - inicio) * 1000
    )
    return linhas
