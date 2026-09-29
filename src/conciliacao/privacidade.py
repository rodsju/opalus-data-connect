"""Nome de paciente: mascarado na tela, revelado só sob demanda.

Tela, relatório, CSV, log e payload de IA levam um código: o ID do paciente no
ERP ('P' + GLBPATIENT.ID) quando a linha casou, ou um pseudônimo estável ('X' +
8 hex de um HMAC do nome normalizado) quando não casou. O HMAC usa um sal do
ambiente (PSEUDONIMO_SAL): sem ele não dá para testar nomes contra o código.

Na interface, ao lado do código, o nome aparece como '*****'. O clique chama
GET /pacientes/nome?codigo=..., que passa por pode_ver_nome() e registra quem
viu qual código. O nome nunca vai no HTML da página.
"""

import hashlib
import hmac
import logging
import os
import re

from . import regras

logger = logging.getLogger(__name__)

_CODIGO = re.compile(r"^(P\d{1,12}|X[0-9A-F]{8})$")


def pseudonimo(nome):
    if not (nome or "").strip():
        return None
    sal = os.getenv("PSEUDONIMO_SAL", "opalus-data-connect").encode()
    return "X" + hmac.new(sal, regras.chave(nome).encode(), hashlib.sha256).hexdigest()[:8].upper()


# Expressão SQL do código exibido (glosa_linha g + cruzamento x)
SQL_CODIGO = "COALESCE('P' || x.id_paciente::text, g.paciente_codigo)"


def pode_ver_nome(usuario):
    """Ponto único da permissão de ver nome. Por ora, todo usuário identificado."""
    # TODO: permissionamento (perfil/grupo com acesso a dado de paciente)
    return True


def nome_paciente(codigo, usuario=None):
    """Código 'P…' (ERP) ou 'X…' (pseudônimo da planilha) -> nome, ou None se não achar.

    PermissionError se o usuário não pode ver; ValueError se o código é inválido.
    """
    codigo = (codigo or "").strip().upper()
    if not _CODIGO.match(codigo):
        raise ValueError("código de paciente inválido")
    if not pode_ver_nome(usuario):
        raise PermissionError("sem permissão para ver o nome do paciente")
    if codigo.startswith("P"):
        from ..reports import fonte
        linhas = fonte.rodar("paciente_nome", {"ID": int(codigo[1:])})
        nome = linhas[0]["nome"] if linhas else None
    else:
        from . import banco
        linha = banco.um("SELECT paciente FROM conciliacao.glosa_linha WHERE paciente_codigo = %s LIMIT 1",
                         (codigo,), "nome do paciente")
        nome = linha["paciente"] if linha else None
    # Auditoria: quem viu qual código (nunca o nome no log)
    logger.info("privacidade: %s revelou o nome do paciente %s (%s)",
                (usuario or {}).get("email") or "anônimo", codigo, "achado" if nome else "não achado")
    return (nome or "").strip() or None


def comentario_pre_auditoria(id_item, usuario=None):
    """Comentário da pré-auditoria de um item (texto livre, pode citar o paciente). Mesmo portão do nome."""
    if not str(id_item or "").isdigit():
        raise ValueError("item inválido")
    if not pode_ver_nome(usuario):
        raise PermissionError("sem permissão para ver o comentário do auditor")
    from ..reports import fonte
    linhas = fonte.rodar("pre_auditoria_comentario", {"ID": int(id_item)})
    texto = (linhas[0]["comentario"] or "").strip() if linhas else ""
    logger.info("privacidade: %s abriu o comentário da pré-auditoria do item %s",
                (usuario or {}).get("email") or "anônimo", id_item)
    return texto or None
