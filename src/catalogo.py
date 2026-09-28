"""Acesso ao catalogo do schema Oracle, gravado no Postgres.

Quem escreve e scripts/mapear_oracle.py; aqui so se le. O modulo devolve dicts
crus -- quem decide rotulo e ordem de coluna e src/oracle.py.
"""

import logging
import math
import os

from . import layout

logger = logging.getLogger(__name__)

DSN = os.getenv("POSTGRES_DSN", "postgresql://catalogo:catalogo@postgres:5432/catalogo")


class ConsultaFalhou(Exception):
    def __init__(self, descricao, causa):
        super().__init__(f"falha na consulta '{descricao}' no catalogo: {causa}")
        self.descricao = descricao
        self.causa = causa


def consultar(sql, params=(), descricao="consulta"):
    """Roda o SELECT e devolve list[dict]. Conecta sob demanda, como o client do BQ:
    sem isso um Postgres fora do ar derrubaria o boot do container."""
    import psycopg
    from psycopg.rows import dict_row

    try:
        with psycopg.connect(DSN, connect_timeout=5) as conexao:
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
    import psycopg

    try:
        with psycopg.connect(DSN, connect_timeout=5) as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(sql, params)
    except Exception as e:
        logger.error("escrita '%s' falhou no catalogo: %s", descricao, e, exc_info=True)
        raise ConsultaFalhou(descricao, e) from e

    logger.info("escrita '%s' concluida", descricao)


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
