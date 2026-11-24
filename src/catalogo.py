"""Acesso ao catalogo do schema Oracle, gravado no Postgres.

Quem escreve e scripts/mapear_oracle.py; aqui so se le. O modulo devolve dicts
crus -- quem decide rotulo e ordem de coluna e src/oracle.py.
"""

import logging
import math
import os
import threading

from . import layout

logger = logging.getLogger(__name__)

DSN = os.getenv("POSTGRES_DSN", "postgresql://catalogo:catalogo@postgres:5432/catalogo")

# No GCP o usuario do banco e a propria SA de runtime (login IAM do Cloud SQL):
# o DSN vem sem senha e a de cada conexao e um access token da SA. Mesmo
# caminho do src/db.py do opalus-atlas-control-app. No local, a senha do DSN.
IAM = os.getenv("DB_IAM_AUTH", "").strip().lower() in ("1", "true", "sim")
ESCOPO_IAM = "https://www.googleapis.com/auth/sqlservice.login"
_credenciais = None
_trava_token = threading.Lock()


def _token():
    """Access token da SA, renovado quando esta para expirar."""
    global _credenciais
    with _trava_token:
        if _credenciais is None:
            import google.auth

            _credenciais, _ = google.auth.default(scopes=[ESCOPO_IAM])
        if not _credenciais.valid:
            from google.auth.transport.requests import Request

            _credenciais.refresh(Request())
        return _credenciais.token


def conectar(dsn=None):
    """Conexao nova; com DB_IAM_AUTH o token da SA vai como senha."""
    import psycopg

    extras = {"password": _token()} if IAM else {}
    return psycopg.connect(dsn or DSN, connect_timeout=5, **extras)


class ConsultaFalhou(Exception):
    def __init__(self, descricao, causa):
        super().__init__(f"falha na consulta '{descricao}' no catalogo: {causa}")
        self.descricao = descricao
        self.causa = causa


def consultar(sql, params=(), descricao="consulta"):
    """Roda o SELECT e devolve list[dict]. Conecta sob demanda, como o client do BQ:
    sem isso um Postgres fora do ar derrubaria o boot do container."""
    from psycopg.rows import dict_row

    try:
        with conectar() as conexao:
            with conexao.cursor(row_factory=dict_row) as cursor:
                cursor.execute(sql, params)
                linhas = cursor.fetchall()
    except Exception as e:
        logger.error("consulta '%s' falhou no catalogo: %s", descricao, e, exc_info=True)
        raise ConsultaFalhou(descricao, e) from e

    logger.info("consulta '%s' devolveu %s linhas", descricao, len(linhas))
    return linhas


def executar(sql, params=(), descricao="escrita"):
    """INSERT/UPDATE. O with da conexao ja faz commit na saida limpa."""
    try:
        with conectar() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql, params)
    except Exception as e:
        logger.error("escrita '%s' falhou no catalogo: %s", descricao, e, exc_info=True)
        raise ConsultaFalhou(descricao, e) from e

    logger.info("escrita '%s' concluida", descricao)


# --------------------------------------------------------------------------
# Migracao no boot
#
# Na nuvem ninguem aplicava o DDL: quem o aplica e o mapeador (--somente-ddl), que
# so roda no local. Um deploy com coluna ou view nova subia contra o schema
# antigo e toda tela dava `column "esquema_id" does not exist` (hml, 24/11/2026).
# Agora o app reaplica o arquivo ao subir -- ele e idempotente, e a SA de runtime
# e a dona do schema catalogo (docs/gcp-setup.md, passo 5.4).
# --------------------------------------------------------------------------

ARQUIVO_DDL = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "catalogo_schema.sql",
)
# Sem isto um ALTER esperaria para sempre por um lock da revisao anterior, que
# continua servindo enquanto esta sobe -- e o boot nunca terminaria.
LOCK_TIMEOUT = "15s"


def aplicar_ddl():
    """Aplica scripts/catalogo_schema.sql numa transacao so. Devolve (ok, detalhe).

    Tudo ou nada: o arquivo vai inteiro num execute, entao uma falha no meio nao
    deixa o schema pela metade. O advisory lock serializa duas instancias subindo
    juntas. Falhar aqui NAO derruba o boot -- o app sobe e as telas mostram o erro
    da consulta, o que e melhor que um container que nem escuta a porta.
    """
    import time

    inicio = time.perf_counter()
    try:
        with open(ARQUIVO_DDL, encoding="utf-8") as arquivo:
            ddl = arquivo.read()
        with conectar() as conexao:
            conexao.execute(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'")
            conexao.execute("SELECT pg_advisory_xact_lock(hashtext('catalogo_ddl'))")
            conexao.execute(ddl)
    except Exception as e:
        logger.error("DDL do catalogo NAO aplicado no boot: %s", e, exc_info=True)
        return False, str(e)
    ms = (time.perf_counter() - inicio) * 1000
    logger.info("DDL do catalogo aplicado no boot em %.0f ms", ms)
    return True, f"{ms:.0f} ms"


def um(sql, params=(), descricao="consulta"):
    """Primeira linha, ou None quando a consulta nao devolve nada."""
    linhas = consultar(sql, params, descricao)
    return linhas[0] if linhas else None


def listar(colunas, origem, campos_busca, termo, pagina, por_pagina, ordem,
           condicao=None, params_condicao=()):
    """Uma pagina de uma listagem, com busca e recorte opcionais.

    `origem` pode trazer JOIN; `campos_busca` sao os campos que o termo varre com
    ILIKE; `condicao` e um predicado SQL que entra em AND com a busca, e
    `params_condicao` sao os valores dos %s dele. Devolve (linhas, pag) -- pag no
    formato que partials/paginacao.html le.

    A ORDEM DOS PARAMETROS importa: o WHERE sai como `condicao AND (busca)`, entao
    os do recorte vem antes dos da busca. Trocar a ordem aqui nao da erro de
    sintaxe -- da resultado errado em silencio.
    """
    condicoes, params = [], list(params_condicao)
    if condicao:
        condicoes.append(condicao)
    if termo:
        alvos = " OR ".join(f"{campo} ILIKE %s" for campo in campos_busca)
        condicoes.append(f"({alvos})")
        params += [f"%{termo}%"] * len(campos_busca)
    filtro = " WHERE " + " AND ".join(condicoes) if condicoes else ""

    total = um(
        f"SELECT count(*) AS total FROM {origem}{filtro}",
        tuple(params),
        "total da listagem",
    )["total"]

    paginas = max(1, math.ceil(total / por_pagina))
    # Pedir uma pagina alem do fim devolve a ultima, nao uma tabela vazia
    pagina = min(max(pagina, 1), paginas)
    deslocamento = (pagina - 1) * por_pagina

    linhas = consultar(
        f"SELECT {colunas} FROM {origem}{filtro} ORDER BY {ordem} LIMIT %s OFFSET %s",
        tuple(params) + (por_pagina, deslocamento),
        f"listagem (pagina {pagina} de {paginas})",
    )

    pag = {
        "pagina": pagina,
        "paginas": paginas,
        "por_pagina": por_pagina,
        "total": total,
        "primeiro": deslocamento + 1 if linhas else 0,
        "ultimo": deslocamento + len(linhas),
        "numeros": layout.numeros_visiveis(pagina, paginas),
    }
    return linhas, pag
