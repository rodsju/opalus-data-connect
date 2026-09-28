"""Identificacao do usuario que ja chega logado.

Em hml/prd o proxy injeta o header x-opalus-user-email. No local nao existe
proxy, entao caimos numa variavel de ambiente de mesmo nome (docker-compose).
"""

import os
import re

HEADER_USUARIO = "x-opalus-user-email"


def iniciais(email):
    # rodrigo.julian@... -> RJ ; suporta ".", "_" e "-" como separadores
    local = email.split("@")[0]
    partes = [p for p in re.split(r"[._-]+", local) if p]
    if len(partes) >= 2:
        return (partes[0][0] + partes[1][0]).upper()
    return local[:2].upper()


def identificar(request):
    """Devolve {'email', 'iniciais'} ou None se ninguem foi identificado."""
    email = (request.headers.get(HEADER_USUARIO) or os.getenv(HEADER_USUARIO) or "").strip()
    if not email:
        return None
    return {"email": email, "iniciais": iniciais(email)}
