"""Configuracao de log da aplicacao.

O Cloud Run le stdout e classifica a linha pelo campo `severity` de um JSON;
sem isso todo log da aplicacao cai como DEFAULT e some no meio do access log do
uvicorn. LOG_LEVEL ja vem no servico do Cloud Run e passa a valer aqui.
"""

import json
import logging
import os
import sys

NIVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Nome do pacote ("src"): os modulos usam getLogger(__name__), entao configurar
# a raiz pega todos eles. Derivado daqui para sobreviver a uma renomeacao.
PACOTE = __name__.split(".")[0]

# Nomes que o Cloud Logging reconhece; WARN/FATAL do logging nao batem
SEVERIDADES = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class FormatadorJson(logging.Formatter):
    """Uma linha JSON por registro, com o traceback em stack_trace."""

    def format(self, record):
        entrada = {
            "severity": record.levelname if record.levelname in SEVERIDADES else "DEFAULT",
            "message": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            entrada["stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(entrada, ensure_ascii=False)


def configurar():
    """Prepara o logger do pacote. Idempotente e sem mexer no do uvicorn."""
    logger = logging.getLogger(PACOTE)
    logger.setLevel(NIVEL)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(FormatadorJson())
        logger.addHandler(handler)
    # Sem isto a mensagem sairia duas vezes: formatada aqui e crua na raiz
    logger.propagate = False
    return logger
