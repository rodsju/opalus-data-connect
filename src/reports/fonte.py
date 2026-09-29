"""Porta única de dados dos /reports.

Os blocos chamam rodar("contas_por_status", params) e recebem list[dict] com
chaves em minúsculo. Qual banco responde é decidido aqui, por REPORTS_FONTE:
"oracle" (default, ao vivo) e, na migração, "bq". Trocar de origem não toca em
bloco nem template -- só num sql_<fonte>.py com as mesmas chaves.
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
    fonte = (os.getenv("REPORTS_FONTE") or "oracle").strip().lower()
    if fonte == "oracle":
        from . import fonte_oracle

        return fonte_oracle
    raise ConsultaFalhou("fonte", f"REPORTS_FONTE='{fonte}' não suportada", "use 'oracle'")


def rodar(nome, params, limite=None):
    # Consultas da Conciliação (carga da planilha) moram no Postgres, qualquer
    # que seja a fonte do ERP.
    from . import sql_pg

    if nome in sql_pg.CONSULTAS:
        from . import fonte_pg as backend
    else:
        backend = _backend()
    inicio = time.perf_counter()
    try:
        linhas = backend.rodar(nome, params, limite=limite)
    except Exception as erro:
        indisponivel = type(erro).__name__ == "OracleIndisponivel"
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
