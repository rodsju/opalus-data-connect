"""Conteudo da rota /health: pagina HTML para humanos, JSON para sondas."""

import logging
import os
import time
from urllib.parse import urlsplit

from . import catalogo, layout

logger = logging.getLogger(__name__)

PAYLOAD = {"status": "healthy"}

# Segundos para o Oracle responder. Curto de proposito: a pagina de health nao
# pode ficar pendurada esperando uma rede que nao chega.
ORACLE_TIMEOUT = 5


def destino_do_catalogo():
    """host:porta/banco do DSN. Monta na mao para nao imprimir a senha."""
    partes = urlsplit(catalogo.DSN)
    return f"{partes.hostname}:{partes.port or 5432}{partes.path}"


# Origens Oracle checadas na pagina: (titulo, prefixo das variaveis no .env).
# Cada prefixo le <PREFIXO>_HOST, _PORT, _SERVICE, _USER, _PASSWORD, _SCHEMA e
# _CLIENT_LIB_DIR.
ORIGENS_ORACLE = [
    ("Origem (Oracle)", "ORACLE"),
    ("Origem Sainte Marie (Oracle, homolog)", "ORACLE_SM"),
]

_cliente_iniciado = False


def destino_do_oracle(prefixo="ORACLE"):
    """host:porta/service da origem. Sem usuario nem senha, como o do catalogo."""
    host = os.getenv(f"{prefixo}_HOST")
    if not host:
        return "não configurado"
    porta = os.getenv(f"{prefixo}_PORT") or "1521"
    return f"{host}:{porta}/{os.getenv(f'{prefixo}_SERVICE') or '?'}"


def checar_oracle(prefixo="ORACLE"):
    """Abre uma conexao na origem e pergunta quem ela acha que somos.

    `SELECT USER FROM dual` em vez de `SELECT 1`: alem de provar que o listener
    responde e que a senha passou, mostra a caixa com que o usuario chegou. E o
    unico jeito de flagrar o ORACLE_USER sem as aspas duplas, que o Oracle
    aceita conectar e depois trata como outro nome.

    Falhar aqui NAO derruba o status HTTP -- ver gerar_pagina().
    """
    faltando = [
        f"{prefixo}_{sufixo}"
        for sufixo in ("HOST", "SERVICE", "USER", "PASSWORD")
        if not os.getenv(f"{prefixo}_{sufixo}")
    ]
    if faltando:
        return False, f"Sem configuração: falta {', '.join(faltando)} no .env.", None

    import oracledb

    global _cliente_iniciado
    inicio = time.perf_counter()
    conexao = None
    try:
        # O modo thick so pode ser ligado uma vez por processo, e vale para
        # todas as conexoes dali em diante.
        lib_dir = os.getenv(f"{prefixo}_CLIENT_LIB_DIR")
        if lib_dir and not _cliente_iniciado:
            oracledb.init_oracle_client(lib_dir=lib_dir)
            _cliente_iniciado = True
        conexao = oracledb.connect(
            user=os.getenv(f"{prefixo}_USER"),
            password=os.getenv(f"{prefixo}_PASSWORD"),
            dsn=destino_do_oracle(prefixo),
            tcp_connect_timeout=ORACLE_TIMEOUT,
        )
        conexao.call_timeout = ORACLE_TIMEOUT * 1000
        with conexao.cursor() as cursor:
            cursor.execute("SELECT USER FROM dual")
            usuario_sessao = cursor.fetchone()[0]
    except Exception as e:
        ms = (time.perf_counter() - inicio) * 1000
        logger.error("Oracle %s nao respondeu em %s: %s", prefixo, destino_do_oracle(prefixo), e)
        # O oracledb costuma anexar linhas de ajuda e um link; a primeira linha
        # e a que diz o que aconteceu.
        return False, str(e).strip().splitlines()[0], ms
    finally:
        if conexao is not None:
            conexao.close()

    ms = (time.perf_counter() - inicio) * 1000
    schema = os.getenv(f"{prefixo}_SCHEMA")
    detalhe = f"Conectado como {usuario_sessao}."
    if schema:
        detalhe += f" Schema mapeado: {schema}."
    return True, detalhe, ms


def checar_catalogo():
    """Le a linha de estado da extracao: prova que o Postgres responde e que o
    catalogo foi populado.

    Nao entra no JSON: sondas de liveness nao devem depender de rede externa.
    """
    inicio = time.perf_counter()
    try:
        extracao = catalogo.um(
            "SELECT schema_origem, status, concluida_em FROM catalogo.extracao WHERE id = 1",
            (),
            "estado do catálogo",
        )
    except catalogo.ConsultaFalhou as falha:
        return False, str(falha.causa), (time.perf_counter() - inicio) * 1000

    ms = (time.perf_counter() - inicio) * 1000
    if not extracao:
        return True, "Catálogo acessível, mas ainda sem extração registrada.", ms
    return (
        True,
        f"Schema {extracao['schema_origem']}, extração {extracao['status']} "
        f"em {layout.fmt(extracao['concluida_em'])}.",
        ms,
    )


def gerar_pagina(usuario=None):
    ok, detalhe, ms = checar_catalogo()
    # `critico` decide duas coisas: a cor da etiqueta e o status HTTP. So o
    # catalogo e critico -- e dele que as paginas leem. O Oracle so e preciso na
    # hora de remapear, e fora da VPN ele e inalcancavel por definicao; marcar
    # ele como critico faria a sonda acusar doente um servico que esta servindo.
    origens = [(titulo, prefixo, *checar_oracle(prefixo)) for titulo, prefixo in ORIGENS_ORACLE]
    oracle_ok = all(o[2] for o in origens)

    checagens = [
        {
            "titulo": "Serviço HTTP",
            "ok": True,
            "critico": True,
            "detalhe": "A aplicação está no ar e respondendo.",
            "ms": None,
        },
        {
            "titulo": "Catálogo (Postgres)",
            "ok": ok,
            "critico": True,
            "detalhe": detalhe,
            "ms": ms,
        },
    ]
    checagens += [
        {"titulo": titulo, "ok": o_ok, "critico": False, "detalhe": o_detalhe, "ms": o_ms}
        for titulo, _, o_ok, o_detalhe, o_ms in origens
    ]
    config = [
        ("Ambiente", layout.AMBIENTE),
        ("Projeto", layout.PROJETO),
        ("Catálogo", destino_do_catalogo()),
        *[(titulo, destino_do_oracle(prefixo)) for titulo, prefixo in ORIGENS_ORACLE],
        ("Usuário identificado", usuario["email"] if usuario else "—"),
    ]

    html = layout.render(
        "health.html",
        "Health",
        usuario,
        "/health",
        catalogo_ok=ok,
        oracle_ok=oracle_ok,
        checagens=checagens,
        config=config,
    )
    return html, 200 if ok else 503
