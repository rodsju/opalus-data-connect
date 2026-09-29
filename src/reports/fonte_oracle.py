"""Backend Oracle dos /reports: conexão somente leitura, uma por consulta.

Mesmo caminho do opalus-mcp-server-01/src/oracle.py: CURRENT_SCHEMA para o
schema do negócio, SET TRANSACTION READ ONLY antes do primeiro SELECT e
call_timeout. Sem pool: os blocos de uma página rodam em paralelo, cada um na
sua conexão, e a página não fica pendurada numa sessão compartilhada.
"""

import os
import re

from . import sql_oracle

NOME_DE_SCHEMA = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")


class OracleIndisponivel(Exception):
    """Não houve conexão. `dica` diz o que provavelmente está errado."""

    def __init__(self, motivo, dica=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.dica = dica


def _sem_aspas_simples(valor):
    # O env_file do docker compose não tira aspas: ORACLE_USER='"rodrigo.julian"'
    # chega literal. As duplas são do Oracle e ficam; o par simples sai.
    if valor and len(valor) >= 2 and valor[0] == valor[-1] == "'":
        return valor[1:-1]
    return valor


def _config():
    faltando = [
        chave
        for chave in ("ORACLE_HOST", "ORACLE_SERVICE", "ORACLE_USER", "ORACLE_PASSWORD")
        if not os.getenv(chave)
    ]
    if faltando:
        raise OracleIndisponivel(
            "conexão com o Oracle não configurada", "faltam no .env: " + ", ".join(faltando)
        )
    return {
        "dsn": f'{os.getenv("ORACLE_HOST")}:{os.getenv("ORACLE_PORT") or "1521"}/'
        f'{os.getenv("ORACLE_SERVICE")}',
        "usuario": _sem_aspas_simples(os.getenv("ORACLE_USER")),
        "senha": _sem_aspas_simples(os.getenv("ORACLE_PASSWORD")),
        "schema": os.getenv("ORACLE_SCHEMA", ""),
        "lib_dir": os.getenv("ORACLE_CLIENT_LIB_DIR", ""),
        "timeout": float(os.getenv("ORACLE_TIMEOUT", "90")),
    }


def _dica(texto, dsn):
    if "DPY-3010" in texto:
        return "servidor anterior ao 12.1: aponte ORACLE_CLIENT_LIB_DIR para o Instant Client"
    if "DPY-6005" in texto or "DPY-4011" in texto or "timeout" in texto.lower():
        return f"não há rota até {dsn} -- a VPN provavelmente está fora"
    if "ORA-01017" in texto:
        return "usuário ou senha recusados (confira as aspas em ORACLE_USER no .env)"
    return texto.strip().splitlines()[0] if texto.strip() else ""


_cliente_iniciado = False


def _conectar(cfg):
    import oracledb

    global _cliente_iniciado
    oracledb.defaults.fetch_lobs = False
    if cfg["lib_dir"] and not _cliente_iniciado:
        oracledb.init_oracle_client(lib_dir=cfg["lib_dir"])
        _cliente_iniciado = True
    try:
        conexao = oracledb.connect(
            user=cfg["usuario"], password=cfg["senha"], dsn=cfg["dsn"], tcp_connect_timeout=8
        )
    except oracledb.Error as erro:
        raise OracleIndisponivel(
            f'não foi possível conectar em {cfg["dsn"]}', _dica(str(erro), cfg["dsn"])
        ) from erro

    conexao.call_timeout = int(cfg["timeout"] * 1000)
    with conexao.cursor() as cursor:
        if cfg["schema"]:
            if not NOME_DE_SCHEMA.match(cfg["schema"]):
                raise OracleIndisponivel("ORACLE_SCHEMA inválido", repr(cfg["schema"]))
            cursor.execute(f'ALTER SESSION SET CURRENT_SCHEMA = {cfg["schema"]}')
        cursor.execute("SET TRANSACTION READ ONLY")
    return conexao


def rodar(nome, params, limite=None):
    """Executa a consulta `nome` de sql_oracle.CONSULTAS; devolve list[dict]."""
    sql = sql_oracle.CONSULTAS[nome]
    # O driver recusa bind que a SQL não usa (DPY-4008): a lista de unidades não
    # tem :UNIDADE, a auditoria não tem período.
    binds = {k: v for k, v in (params or {}).items() if f":{k}" in sql}
    # Lista vira IN (:NOME_0, :NOME_1, ...): o driver não expande sozinho, e
    # concatenar os valores na SQL abriria injeção. Teto de 1000 itens do Oracle.
    for nome, valor in list(binds.items()):
        if isinstance(valor, (list, tuple)):
            if not 0 < len(valor) <= 1000:
                raise ValueError(f"lista :{nome} precisa ter de 1 a 1000 itens (veio {len(valor)})")
            del binds[nome]
            nomes = [f"{nome}_{i}" for i in range(len(valor))]
            binds.update(zip(nomes, valor))
            sql = re.sub(rf":{nome}\b", ", ".join(f":{n}" for n in nomes), sql)
    if limite:
        sql = f"SELECT * FROM ({sql}) WHERE ROWNUM <= :LIMITE_REPORTS"
        binds["LIMITE_REPORTS"] = int(limite)

    conexao = _conectar(_config())
    try:
        with conexao.cursor() as cursor:
            cursor.execute(sql, binds)
            colunas = [c[0].lower() for c in cursor.description]
            return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    finally:
        conexao.close()
