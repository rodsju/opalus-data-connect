#!/usr/bin/env python3
"""Mapeia um schema Oracle e grava o catalogo de dados num Postgres.

Para cada tabela/view do schema le colunas e tipos, chaves (PK/UK/FK), indices,
comentarios, quantos registros tem e uma amostra de 100 linhas. O resultado vai
para o schema `catalogo` do Postgres definido em POSTGRES_DSN, cujo DDL esta em
scripts/catalogo_schema.sql.

No Oracle o script so emite SELECT; nunca escreve nada la.

Uso tipico (com a VPN ligada, porque o banco fica em outra rede):

    make catalogo ARGS="--limite 3"      # smoke test
    make catalogo                        # schema inteiro
    make amostras                        # so as amostras, sem tocar no resto

Os drivers (oracledb, psycopg) sao importados sob demanda para as funcoes puras
continuarem testaveis num ambiente sem eles instalados.

--------------------------------------------------------------------------
A amostra
--------------------------------------------------------------------------

O valor vai para o catalogo COMO ESTA na origem. Nao ha mascaramento -- o que
existia decidia pelo nome da coluna, por substring sem ancora, e errava dos dois
lados: "RG" casava CD_ORGAO e CIRURGIA, enquanto numero nunca era mascarado, o
que deixava passar CPF gravado como NUMBER. A coluna catalogo.amostra.mascarada
sobreviveu por compatibilidade e hoje e sempre false.

Consequencia a ter em conta: a amostra e o dado real, e ela aparece na tela e vai
no prompt para o provedor de IA configurado.

A amostra tenta trazer os registros MAIS RECENTES, mas so quando da para ordenar
barato -- sao 930 milhoes de linhas neste schema. Quem decide e escolher_ordem();
medido no schema, 1.276 dos 1.649 objetos com registros ganham ordem, e a maior
tabela (341 milhoes de linhas) devolve 100 linhas em 173 ms.

BLOB entra como resumo (tamanho + os primeiros bytes em hex, o bastante para
reconhecer PDF/JPEG/PNG), sem trafegar o binario. CLOB e NCLOB entram como texto
truncado em LIMITE_TEXTO. LONG continua de fora: quebra o fetch.

--------------------------------------------------------------------------
--somente-amostras: o que ele NAO faz
--------------------------------------------------------------------------

Refazer amostra pelo caminho normal sairia caro: gravar_objeto() apaga e reinsere
restricao, indice e relacionamento, e poe atualizado_em = now() -- e esse
timestamp e comparado com descricao_ia.gerado_em para decidir se a descricao esta
vencida, entao um mapeamento completo marcaria todas as descricoes ja pagas como
desatualizadas sem nada de estrutural ter mudado.

Com --somente-amostras a escrita e gravar_amostra(), que mexe so em
catalogo.amostra e em objeto.tem_registros. Descricao de IA, embeddings,
estrutura e atualizado_em ficam intactos. Amostra que falha nao apaga a que
estava la, e objeto que ainda nao existe no catalogo e pulado -- este modo refaz
amostra, nao descobre tabela nova.
"""

import argparse
import datetime
import decimal
import fnmatch
import logging
import os
import pathlib
import socket
import sys

logger = logging.getLogger("mapear_oracle")

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ARQUIVO_DDL = pathlib.Path(__file__).resolve().parent / "catalogo_schema.sql"

# Tipos que ficam fora do SELECT da amostra: LONG quebra o fetch, o resto nao
# tem como virar texto. BLOB NAO esta aqui -- ele entra como resumo, ver
# expressao_blob(). Tipo de objeto do usuario e detectado pelo DATA_TYPE_OWNER
# preenchido, nao por esta lista.
TIPOS_FORA_DA_AMOSTRA = {"LONG", "LONG RAW", "BFILE", "XMLTYPE", "ANYDATA"}

# Quantos bytes do inicio do BLOB trazer em hex. 16 bastam para reconhecer o
# formato do arquivo: 25504446 = PDF, FFD8FF = JPEG, 89504E47 = PNG.
BYTES_DO_BLOB = 16

# Acima disto uma tabela sem indice util nao e ordenada: o ORDER BY viraria full
# scan + sort no Oracle de producao, e a maior tabela deste schema tem 341
# milhoes de linhas. Ver escolher_ordem().
TETO_ORDENACAO_CARA = 100_000

# Coluna de data que melhor representa "registro recente", em ordem de
# preferencia. Sao os nomes que existem neste schema; fora da lista vale a
# primeira DATE por posicao.
DATAS_PREFERIDAS = ("CREATIONDATETIME", "CREATIONDATE", "EVENTDATE", "LASTEDITIONDATETIME")

# Texto acima disso sai truncado: amostra e para entender o formato do dado,
# nao para carregar um laudo inteiro para dentro do catalogo.
LIMITE_TEXTO = 500


# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------


def tirar_aspas(valor):
    """Remove UM par de aspas ao redor do valor, e so ele.

    Nao da para sair tirando aspas em serie: senha que termina em aspas seria
    mutilada, e o par interno precisa sobreviver. Com um par so, da para pedir
    aspas de proposito escrevendo ORACLE_USER=\'"meuUser"\' -- as simples saem,
    as duplas chegam ao Oracle e viram identificador case-sensitive.
    """
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
        return valor[1:-1]
    return valor


def carregar_env(caminho):
    """Le um .env simples (CHAVE=valor) sem sobrescrever o ambiente ja definido."""
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        # Sem tratamento de comentario no fim da linha de proposito: '#' e
        # caractere comum em senha, e engolir o resto da linha quebraria ela.
        valor = tirar_aspas(valor.strip())
        # Variavel exportada no shell vence o arquivo
        os.environ.setdefault(chave.strip(), valor)


# ---------------------------------------------------------------------------
# Funcoes puras: conversao de valor, escolha da ordem, montagem do SELECT
#
# Nao ha mascaramento aqui, e a ausencia e deliberada. O que existia decidia pelo
# NOME da coluna, por substring sem ancora: "RG" casava CD_ORGAO e CIRURGIA, e
# numero nunca era mascarado em modo nenhum -- entao CPF gravado como NUMBER saia
# inteiro enquanto CD_ORGAO virava xx. Errava dos dois lados, e o pior e que a
# coluna amostra.mascarada dizia "true" para tudo, dando uma garantia falsa.
# ---------------------------------------------------------------------------


def converter_valor(valor):
    """Converte o que o Oracle devolve para algo que vira jsonb."""
    if valor is None or isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        if len(valor) > LIMITE_TEXTO:
            return valor[:LIMITE_TEXTO] + f"... <truncado, {len(valor)} caracteres>"
        return valor
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        # jsonb nao aceita NaN/Infinity
        return valor if valor == valor and abs(valor) != float("inf") else str(valor)
    if isinstance(valor, decimal.Decimal):
        if not valor.is_finite():
            return str(valor)
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor.isoformat()
    if isinstance(valor, datetime.timedelta):
        return str(valor)
    if isinstance(valor, (bytes, bytearray)):
        return f"<BINARIO {len(valor)} bytes>"
    return str(valor)


def citar(identificador):
    """Identificador Oracle entre aspas, com aspas internas dobradas."""
    return '"' + str(identificador).replace('"', '""') + '"'


def tipo_completo(coluna):
    """Reconstroi o tipo como se le no DDL: NUMBER(10,2), VARCHAR2(60 CHAR)."""
    tipo = coluna["tipo"]
    if tipo in ("VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR"):
        tamanho = coluna.get("char_length") or coluna.get("tamanho")
        unidade = " CHAR" if coluna.get("char_used") == "C" else " BYTE"
        if tipo.startswith("N"):
            unidade = ""  # tipo nacional ja e por caractere
        return f"{tipo}({tamanho}{unidade})" if tamanho else tipo
    if tipo == "NUMBER":
        precisao, escala = coluna.get("precisao"), coluna.get("escala")
        if precisao is None:
            return "NUMBER"
        return f"NUMBER({precisao})" if not escala else f"NUMBER({precisao},{escala})"
    if tipo in ("RAW", "UROWID"):
        return f"{tipo}({coluna['tamanho']})" if coluna.get("tamanho") else tipo
    # TIMESTAMP(6), INTERVAL DAY(2) TO SECOND(6) etc. ja vem completos do dicionario
    return tipo


def entra_na_amostra(coluna):
    """Tipo de objeto do usuario tem DATA_TYPE_OWNER preenchido; os demais na lista."""
    if coluna.get("tipo_owner"):
        return False
    return coluna["tipo"] not in TIPOS_FORA_DA_AMOSTRA


def escolher_ordem(colunas, chaves_pk, indices, num_registros):
    """Por qual coluna pegar os registros MAIS RECENTES. Devolve o nome ou None.

    A amostra sem ORDER BY traz as primeiras linhas fisicas -- num sistema com
    historico, os registros mais antigos. Mas ordenar custa caro: sao 930 milhoes
    de linhas neste schema, e a maior tabela tem 341 milhoes. Entao so ordena
    quando ha um caminho barato:

    1. PK numerica de uma coluna. E o caso comum (953 dos 1.649 objetos com
       registros) e o mais barato de todos: o indice da PK sempre existe, e o
       Oracle resolve o top-N com scan reverso, sem sort nenhum. Vale como
       "recente" porque o ID vem de sequence -- medido nas amostras atuais, a
       correlacao entre ID e CREATIONDATE fica entre 0,93 e 0,999.
    2. Coluna DATE que lidera um indice. Mesmo motivo, sem o sort.
    3. Coluna DATE sem indice, mas so em tabela pequena: aqui o sort acontece de
       verdade, e TETO_ORDENACAO_CARA e o que impede de rodar isso num monstro.
    4. Nada. Fica como sempre foi, com as primeiras linhas.

    View cai sempre no caso 4: nao tem PK nem indice, e num_registros vem None
    (nao sai de ALL_TABLES), o que ja a reprova na regra 3.
    """
    por_nome = {c["nome"]: c for c in colunas}

    if len(chaves_pk) == 1:
        pk = next(iter(chaves_pk))
        coluna = por_nome.get(pk)
        if coluna and coluna["tipo"] in ("NUMBER", "FLOAT"):
            return pk

    datas = [c["nome"] for c in colunas if c["tipo"] == "DATE"]
    if not datas:
        return None

    def preferida(candidatas):
        for nome in DATAS_PREFERIDAS:
            if nome in candidatas:
                return nome
        return candidatas[0]

    lideram_indice = [d for d in datas if any(i["colunas"][:1] == [d] for i in indices)]
    if lideram_indice:
        return preferida(lideram_indice)

    if num_registros is not None and num_registros < TETO_ORDENACAO_CARA:
        return preferida(datas)
    return None


def expressao_blob(nome):
    """BLOB vira um resumo de uma linha, nao o binario.

    Puxar um LOB de megabytes para dizer o tamanho dele seria desperdicio, entao
    o proprio Oracle monta o resumo. Sai uma coluna de saida por coluna da
    tabela, com o mesmo nome, no formato que converter_valor ja usa para bytes.
    """
    col = citar(nome)
    return (
        f"CASE WHEN {col} IS NULL THEN NULL ELSE "
        f"'<BINARIO ' || DBMS_LOB.GETLENGTH({col}) || ' bytes, hex ' || "
        f"RAWTOHEX(DBMS_LOB.SUBSTR({col}, {BYTES_DO_BLOB}, 1)) || '>' END AS {col}"
    )


def montar_select_amostra(schema, objeto, colunas, limite, ordem=None):
    """Monta o SELECT da amostra. Devolve (sql, nomes) ou (None, []) se nada resta.

    Lista explicita em vez de SELECT *, para pular os tipos que quebram o fetch.
    ROWNUM em vez de FETCH FIRST, para funcionar em qualquer versao do Oracle.

    O ROWNUM fica FORA do subselect, e isso nao e estilo. No Oracle o ROWNUM e
    atribuido ANTES do ORDER BY: "WHERE ROWNUM <= 100 ORDER BY ID DESC" pega as
    100 primeiras linhas fisicas e ordena so essas 100 -- daria a impressao de
    estar ordenado trazendo exatamente os registros antigos que queremos evitar.
    """
    usaveis = [c for c in colunas if c.get("na_amostra")]
    if not usaveis:
        return None, []
    lista = ", ".join(
        expressao_blob(c["nome"]) if c["tipo"] == "BLOB" else citar(c["nome"])
        for c in usaveis
    )
    corpo = f"SELECT {lista} FROM {citar(schema)}.{citar(objeto)}"
    if ordem:
        corpo += f" ORDER BY {citar(ordem)} DESC"
    sql = f"SELECT * FROM ({corpo}) WHERE ROWNUM <= {int(limite)}"
    return sql, [c["nome"] for c in usaveis]


def resolver_relacionamentos(restricoes, colunas_por_constraint, tabela_por_constraint):
    """Transforma as constraints do tipo R em arestas do grafo.

    `restricoes` sao as linhas de ALL_CONSTRAINTS do schema; os dois dicionarios
    sao indexados por (owner, constraint_name) e ja incluem os owners externos,
    porque em base legada a FK as vezes aponta para fora do schema.
    """
    arestas = []
    nao_resolvidas = []
    for r in restricoes:
        if r["tipo"] != "R":
            continue
        chave = (r["ref_owner"], r["ref_constraint"])
        destino_tabela = tabela_por_constraint.get(chave)
        destino_colunas = colunas_por_constraint.get(chave)
        origem_colunas = colunas_por_constraint.get((r["owner"], r["nome"]), [])
        if not destino_tabela or not destino_colunas:
            nao_resolvidas.append(r["nome"])
            continue
        arestas.append(
            {
                "constraint_nome": r["nome"],
                "origem_tabela": r["tabela"],
                "origem_colunas": origem_colunas,
                "destino_schema": r["ref_owner"],
                "destino_tabela": destino_tabela,
                "destino_colunas": destino_colunas,
                "delete_rule": r.get("delete_rule"),
            }
        )
    return arestas, nao_resolvidas


def gerar_mermaid(arestas):
    """Diagrama ER em Mermaid a partir das arestas ja resolvidas."""
    linhas = ["erDiagram"]
    for a in sorted(arestas, key=lambda x: (x["origem_tabela"], x["constraint_nome"])):
        rotulo = ",".join(a["origem_colunas"]) or a["constraint_nome"]
        linhas.append(f'    {a["destino_tabela"]} ||--o{{ {a["origem_tabela"]} : "{rotulo}"')
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------------------
# Leitura do dicionario Oracle
# ---------------------------------------------------------------------------


def conectar_oracle(host, porta, service, usuario, senha, timeout, lib_dir):
    import oracledb

    # CLOB chega como str em vez de handle; sem isso a amostra viria com objetos
    # que morrem junto com o cursor.
    oracledb.defaults.fetch_lobs = False
    if lib_dir:
        oracledb.init_oracle_client(lib_dir=lib_dir)

    dsn = f"{host}:{porta}/{service}"
    try:
        conexao = oracledb.connect(user=usuario, password=senha, dsn=dsn)
    except oracledb.Error as erro:
        if "DPY-3010" in str(erro) and not lib_dir:
            logger.error(
                "O servidor e anterior ao Oracle 12.1 e o modo thin nao atende. "
                "Instale o Oracle Instant Client e aponte ORACLE_CLIENT_LIB_DIR "
                "para o diretorio dele no .env."
            )
        raise
    conexao.call_timeout = int(timeout * 1000)
    return conexao


def _linhas(cur):
    """Cursor Oracle como lista de dicts com as chaves em minusculo."""
    nomes = [d[0].lower() for d in cur.description]
    return [dict(zip(nomes, linha)) for linha in cur.fetchall()]


def ler_tabelas(cur, schema):
    # nested='NO' e o filtro de IOT_OVERFLOW tiram os segmentos internos, que
    # aparecem em ALL_TABLES mas nao sao tabela de verdade
    cur.execute(
        """
        SELECT table_name, num_rows, last_analyzed, partitioned
          FROM all_tables
         WHERE owner = :owner
           AND table_name NOT LIKE 'BIN$%'
           AND nested = 'NO'
           AND (iot_type IS NULL OR iot_type = 'IOT')
         ORDER BY table_name
        """,
        {"owner": schema},
    )
    return _linhas(cur)


def ler_views(cur, schema):
    cur.execute(
        "SELECT view_name FROM all_views WHERE owner = :owner ORDER BY view_name",
        {"owner": schema},
    )
    return [linha["view_name"] for linha in _linhas(cur)]


def ler_sql_da_view(cur, schema, nome):
    """ALL_VIEWS.TEXT e LONG: lido uma view por vez, fetch em lote se atrapalha."""
    cur.execute(
        "SELECT text FROM all_views WHERE owner = :owner AND view_name = :nome",
        {"owner": schema, "nome": nome},
    )
    linha = cur.fetchone()
    return linha[0] if linha and linha[0] else None


def ler_colunas(cur, schema):
    """Colunas agrupadas por tabela. DATA_DEFAULT vem por ultimo porque e LONG."""
    base = """
        SELECT table_name, column_name, column_id, data_type, data_type_owner,
               data_length, data_precision, data_scale, nullable,
               char_length, char_used{default_col}
          FROM all_tab_columns
         WHERE owner = :owner
         ORDER BY table_name, column_id
    """
    avisos = []
    try:
        cur.execute(base.format(default_col=", data_default"), {"owner": schema})
        cruas = _linhas(cur)
    except Exception as erro:  # noqa: BLE001 - qualquer falha no LONG cai no plano B
        logger.warning("nao consegui ler DATA_DEFAULT (%s); seguindo sem os defaults", erro)
        avisos.append(f"DATA_DEFAULT nao lido: {erro}")
        cur.execute(base.format(default_col=""), {"owner": schema})
        cruas = _linhas(cur)

    por_tabela = {}
    for linha in cruas:
        valor_default = linha.get("data_default")
        coluna = {
            "posicao": linha["column_id"] or 0,
            "nome": linha["column_name"],
            "tipo": linha["data_type"],
            "tipo_owner": linha["data_type_owner"],
            "tamanho": linha["data_length"],
            "precisao": linha["data_precision"],
            "escala": linha["data_scale"],
            "char_length": linha["char_length"],
            "char_used": linha["char_used"],
            "aceita_nulo": linha["nullable"] == "Y",
            "valor_default": str(valor_default).strip() if valor_default is not None else None,
            "comentario": None,
            "eh_pk": False,
        }
        coluna["tipo_completo"] = tipo_completo(coluna)
        coluna["na_amostra"] = entra_na_amostra(coluna)
        por_tabela.setdefault(linha["table_name"], []).append(coluna)
    return por_tabela, avisos


def ler_comentarios(cur, schema):
    cur.execute(
        "SELECT table_name, comments FROM all_tab_comments WHERE owner = :owner",
        {"owner": schema},
    )
    de_tabela = {l["table_name"]: l["comments"] for l in _linhas(cur) if l["comments"]}

    cur.execute(
        "SELECT table_name, column_name, comments FROM all_col_comments WHERE owner = :owner",
        {"owner": schema},
    )
    de_coluna = {
        (l["table_name"], l["column_name"]): l["comments"]
        for l in _linhas(cur)
        if l["comments"]
    }
    return de_tabela, de_coluna


def _consultar_constraints(cur, owners):
    marcadores = {f"o{i}": o for i, o in enumerate(owners)}
    lista = ", ".join(f":{k}" for k in marcadores)
    cur.execute(
        f"""
        SELECT owner, constraint_name, constraint_type, table_name,
               r_owner, r_constraint_name, delete_rule, status
          FROM all_constraints
         WHERE owner IN ({lista})
           AND constraint_type IN ('P', 'U', 'R')
           AND table_name NOT LIKE 'BIN$%'
        """,
        marcadores,
    )
    return _linhas(cur)


def _consultar_cons_colunas(cur, owners):
    marcadores = {f"o{i}": o for i, o in enumerate(owners)}
    lista = ", ".join(f":{k}" for k in marcadores)
    cur.execute(
        f"""
        SELECT owner, constraint_name, column_name, position
          FROM all_cons_columns
         WHERE owner IN ({lista})
         ORDER BY owner, constraint_name, NVL(position, 1)
        """,
        marcadores,
    )
    return _linhas(cur)


def ler_restricoes(cur, schema):
    """Constraints do schema + o que for preciso dos owners externos.

    FK apontando para fora do schema acontece em base legada; sem buscar o owner
    de destino a aresta ficaria sem tabela nem coluna.
    """
    cruas = _consultar_constraints(cur, [schema])

    externos = {
        l["r_owner"]
        for l in cruas
        if l["constraint_type"] == "R" and l["r_owner"] and l["r_owner"] != schema
    }
    todas = list(cruas)
    if externos:
        todas += _consultar_constraints(cur, sorted(externos))

    colunas_por_constraint = {}
    for linha in _consultar_cons_colunas(cur, [schema] + sorted(externos)):
        chave = (linha["owner"], linha["constraint_name"])
        colunas_por_constraint.setdefault(chave, []).append(linha["column_name"])

    tabela_por_constraint = {
        (l["owner"], l["constraint_name"]): l["table_name"] for l in todas
    }

    restricoes = [
        {
            "owner": l["owner"],
            "nome": l["constraint_name"],
            "tipo": l["constraint_type"],
            "tabela": l["table_name"],
            "ref_owner": l["r_owner"],
            "ref_constraint": l["r_constraint_name"],
            "delete_rule": l["delete_rule"],
            "status": l["status"],
        }
        for l in cruas
    ]
    return restricoes, colunas_por_constraint, tabela_por_constraint


def ler_indices(cur, schema):
    cur.execute(
        """
        SELECT index_name, table_name, uniqueness, index_type
          FROM all_indexes
         WHERE table_owner = :owner
           AND table_name NOT LIKE 'BIN$%'
        """,
        {"owner": schema},
    )
    cabecalhos = _linhas(cur)

    cur.execute(
        """
        SELECT index_name, table_name, column_name, column_position
          FROM all_ind_columns
         WHERE table_owner = :owner
         ORDER BY index_name, column_position
        """,
        {"owner": schema},
    )
    colunas = {}
    for linha in _linhas(cur):
        colunas.setdefault(linha["index_name"], []).append(linha["column_name"])

    por_tabela = {}
    for linha in cabecalhos:
        por_tabela.setdefault(linha["table_name"], []).append(
            {
                "nome": linha["index_name"],
                "unico": linha["uniqueness"] == "UNIQUE",
                "tipo": linha["index_type"],
                "colunas": colunas.get(linha["index_name"], []),
            }
        )
    return por_tabela


def contar_exato(cur, schema, nome):
    cur.execute(f"SELECT COUNT(*) FROM {citar(schema)}.{citar(nome)}")
    return cur.fetchone()[0]


def coletar_amostra(cur, schema, nome, colunas, limite, ordem=None):
    """Devolve os registros prontos para virar jsonb, sem mascaramento nenhum."""
    sql, nomes = montar_select_amostra(schema, nome, colunas, limite, ordem)
    if not sql:
        return []
    cur.execute(sql)
    registros = []
    for linha in cur.fetchall():
        registros.append(
            {nome_col: converter_valor(valor) for nome_col, valor in zip(nomes, linha)}
        )
    return registros


# ---------------------------------------------------------------------------
# Gravacao no Postgres
# ---------------------------------------------------------------------------


def conectar_pg(dsn):
    import psycopg

    return psycopg.connect(dsn)


def aplicar_ddl(conexao):
    conexao.execute(ARQUIVO_DDL.read_text(encoding="utf-8"))
    conexao.commit()


def abrir_extracao(conexao, schema, host, service, parametros):
    from psycopg.types.json import Json

    conexao.execute(
        """
        INSERT INTO catalogo.extracao
            (id, schema_origem, host, service_name, iniciada_em, status, parametros, erros)
        VALUES (1, %s, %s, %s, now(), 'em_andamento', %s, '[]'::jsonb)
        ON CONFLICT (id) DO UPDATE SET
            schema_origem = EXCLUDED.schema_origem,
            host          = EXCLUDED.host,
            service_name  = EXCLUDED.service_name,
            iniciada_em   = now(),
            concluida_em  = NULL,
            status        = 'em_andamento',
            parametros    = EXCLUDED.parametros,
            erros         = '[]'::jsonb
        """,
        (schema, host, service, Json(parametros)),
    )
    conexao.commit()


def fechar_extracao(conexao, status, erros):
    from psycopg.types.json import Json

    conexao.execute(
        "UPDATE catalogo.extracao SET concluida_em = now(), status = %s, erros = %s WHERE id = 1",
        (status, Json(erros)),
    )
    conexao.commit()


def garantir_esquema(conexao, tipo, host, porta, base, schema):
    """Upsert do servidor e do esquema do .env. Devolve o esquema_id.

    O DDL ja faz o backfill de um banco que veio da versao sem hierarquia, lendo
    catalogo.extracao. Esta funcao e o outro caso: banco novo, onde nao ha
    extracao de onde herdar, e toda execucao seguinte, onde ela so confirma.
    """
    with conexao.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalogo.servidor (tipo, host, porta, base, nome)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tipo, host, porta, base) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (tipo, host, int(porta), base, f"{host}/{base}"),
        )
        servidor_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO catalogo.esquema (servidor_id, nome) VALUES (%s, %s)
            ON CONFLICT (servidor_id, nome) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (servidor_id, schema),
        )
        esquema_id = cur.fetchone()[0]
    conexao.commit()
    return esquema_id


def nomes_ja_gravados(conexao, esquema_id):
    """So os nomes DESTE esquema.

    Sem o filtro, mapear um segundo schema veria os nomes do primeiro e
    --pular-existentes pularia o schema inteiro sem gravar nada.
    """
    return {
        linha[0]
        for linha in conexao.execute(
            "SELECT nome FROM catalogo.objeto WHERE esquema_id = %s", (esquema_id,)
        )
    }


def gravar_objeto(conexao, objeto, arestas):
    """Grava um objeto e seus filhos numa transacao so.

    Sem TRUNCATE no inicio da execucao: o upsert por objeto mantem a foto
    corrente e, com commit por objeto, uma queda de VPN no meio nao perde o que
    ja foi mapeado.
    """
    from psycopg.types.json import Json

    with conexao.cursor() as cur:
        cur.execute(
            """
            INSERT INTO catalogo.objeto
                (esquema_id, nome, tipo, comentario, num_registros, contagem_aproximada,
                 contagem_coletada_em, tem_registros, particionada, view_sql,
                 atualizado_em, erros)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)
            ON CONFLICT (esquema_id, nome) DO UPDATE SET
                tipo                 = EXCLUDED.tipo,
                comentario           = EXCLUDED.comentario,
                num_registros        = EXCLUDED.num_registros,
                contagem_aproximada  = EXCLUDED.contagem_aproximada,
                contagem_coletada_em = EXCLUDED.contagem_coletada_em,
                tem_registros        = EXCLUDED.tem_registros,
                particionada         = EXCLUDED.particionada,
                view_sql             = EXCLUDED.view_sql,
                atualizado_em        = now(),
                erros                = EXCLUDED.erros
            RETURNING id
            """,
            (
                objeto["esquema_id"],
                objeto["nome"],
                objeto["tipo"],
                objeto.get("comentario"),
                objeto.get("num_registros"),
                objeto.get("contagem_aproximada", True),
                objeto.get("contagem_coletada_em"),
                objeto.get("tem_registros"),
                objeto.get("particionada"),
                objeto.get("view_sql"),
                Json(objeto.get("erros", [])),
            ),
        )
        objeto_id = cur.fetchone()[0]

        for filha in ("restricao", "indice", "amostra"):
            cur.execute(f"DELETE FROM catalogo.{filha} WHERE objeto_id = %s", (objeto_id,))

        # coluna NAO entra na lista acima: ela carrega descricao_ia e o embedding,
        # que sao escritos pelo app. Apagar e reinserir, como as outras filhas,
        # jogaria fora todo o trabalho de IA a cada mapeamento. O upsert atualiza
        # so o que vem do Oracle -- o DO UPDATE SET nao toca nas colunas de IA.
        colunas = objeto.get("colunas", [])
        cur.executemany(
            """
            INSERT INTO catalogo.coluna
                (objeto_id, posicao, nome, tipo, tipo_completo, tamanho, precisao,
                 escala, aceita_nulo, valor_default, comentario, eh_pk, na_amostra)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (objeto_id, nome) DO UPDATE SET
                posicao       = EXCLUDED.posicao,
                tipo          = EXCLUDED.tipo,
                tipo_completo = EXCLUDED.tipo_completo,
                tamanho       = EXCLUDED.tamanho,
                precisao      = EXCLUDED.precisao,
                escala        = EXCLUDED.escala,
                aceita_nulo   = EXCLUDED.aceita_nulo,
                valor_default = EXCLUDED.valor_default,
                comentario    = EXCLUDED.comentario,
                eh_pk         = EXCLUDED.eh_pk,
                na_amostra    = EXCLUDED.na_amostra
            """,
            [
                (
                    objeto_id, c["posicao"], c["nome"], c["tipo"], c["tipo_completo"],
                    c.get("tamanho"), c.get("precisao"), c.get("escala"),
                    c["aceita_nulo"], c.get("valor_default"), c.get("comentario"),
                    c.get("eh_pk", False), c.get("na_amostra", True),
                )
                for c in colunas
            ],
        )

        # O upsert sozinho nunca remove: coluna dropada no Oracle ficaria no
        # catalogo para sempre. Esta e a outra metade do DELETE que saiu acima.
        #
        # So poda com lista NAO VAZIA. Tabela sem coluna nenhuma nao existe no
        # Oracle: lista vazia significa que a leitura falhou, nao que dropar am
        # todas as colunas. Sem esta guarda, `colunas_por_tabela.get(nome, [])`
        # devolvendo [] apaga as colunas do objeto -- e com elas a descricao de
        # campo, os embeddings e as flags de sensibilidade. Aconteceu: CAPADMISSION
        # perdeu 194 colunas assim.
        if colunas:
            cur.execute(
                "DELETE FROM catalogo.coluna WHERE objeto_id = %s AND nome <> ALL(%s)",
                (objeto_id, [c["nome"] for c in colunas]),
            )

        cur.executemany(
            """
            INSERT INTO catalogo.restricao
                (objeto_id, nome, tipo, colunas, ref_schema, ref_tabela,
                 ref_colunas, delete_rule, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    objeto_id, r["nome"], r["tipo"], r["colunas"], r.get("ref_schema"),
                    r.get("ref_tabela"), r.get("ref_colunas"), r.get("delete_rule"),
                    r.get("status"),
                )
                for r in objeto.get("restricoes", [])
            ],
        )

        cur.executemany(
            "INSERT INTO catalogo.indice (objeto_id, nome, unico, tipo, colunas) "
            "VALUES (%s, %s, %s, %s, %s)",
            [
                (objeto_id, i["nome"], i["unico"], i.get("tipo"), i["colunas"])
                for i in objeto.get("indices", [])
            ],
        )

        cur.executemany(
            "INSERT INTO catalogo.amostra (objeto_id, linha, mascarada, dados) "
            "VALUES (%s, %s, %s, %s)",
            [
                (objeto_id, n, False, Json(registro))
                for n, registro in enumerate(objeto.get("amostra", []), start=1)
            ],
        )

        # Escopado no esquema: sem isso o DELETE levaria junto as arestas da
        # tabela homonima de outro schema.
        cur.execute(
            "DELETE FROM catalogo.relacionamento "
            " WHERE esquema_id = %s AND origem_tabela = %s",
            (objeto["esquema_id"], objeto["nome"]),
        )
        cur.executemany(
            """
            INSERT INTO catalogo.relacionamento
                (esquema_id, constraint_nome, origem_tabela, origem_colunas,
                 destino_schema, destino_tabela, destino_colunas, delete_rule)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    objeto["esquema_id"],
                    a["constraint_nome"], a["origem_tabela"], a["origem_colunas"],
                    a["destino_schema"], a["destino_tabela"], a["destino_colunas"],
                    a.get("delete_rule"),
                )
                for a in arestas
            ],
        )
    conexao.commit()


def gravar_amostra(conexao, esquema_id, nome, amostra):
    """Troca SO a amostra de um objeto que ja existe. Devolve True se gravou.

    E a metade de gravar_objeto que o modo --somente-amostras usa, e o que ela
    NAO faz e o ponto todo. gravar_objeto apaga e reinsere restricao, indice e
    relacionamento, e poe atualizado_em = now() -- e esse timestamp e comparado
    com descricao_ia.gerado_em para decidir se a descricao esta vencida, entao um
    mapeamento completo so para refazer amostra marcaria as 2.266 descricoes
    como desatualizadas sem que nada de estrutural tivesse mudado.

    Objeto que ainda nao esta no catalogo e ignorado: este modo refaz amostra,
    nao descobre tabela nova -- para isso serve o mapeamento completo.
    """
    from psycopg.types.json import Json

    with conexao.cursor() as cur:
        cur.execute(
            "SELECT id FROM catalogo.objeto WHERE esquema_id = %s AND nome = %s",
            (esquema_id, nome),
        )
        linha = cur.fetchone()
        if not linha:
            return False
        objeto_id = linha[0]

        cur.execute("DELETE FROM catalogo.amostra WHERE objeto_id = %s", (objeto_id,))
        cur.executemany(
            "INSERT INTO catalogo.amostra (objeto_id, linha, mascarada, dados) "
            "VALUES (%s, %s, %s, %s)",
            [
                (objeto_id, n, False, Json(registro))
                for n, registro in enumerate(amostra, start=1)
            ],
        )
        # tem_registros sai da amostra, nao da estatistica do Oracle, e alimenta
        # os recortes "com registros" da tela e do grafo -- por isso acompanha.
        cur.execute(
            "UPDATE catalogo.objeto SET tem_registros = %s WHERE id = %s",
            (len(amostra) > 0, objeto_id),
        )
    conexao.commit()
    return True


# Em constante, e nao inline, para o teste poder afirmar sobre o WHERE: e o SQL
# mais perigoso do arquivo e o unico jeito de cobri-lo sem um banco no pytest.
SQL_REMOVER_OBJETOS = """
DELETE FROM catalogo.objeto
 WHERE esquema_id = %s AND NOT (nome = ANY(%s))
 RETURNING nome
"""

SQL_REMOVER_RELACIONAMENTOS = """
DELETE FROM catalogo.relacionamento
 WHERE esquema_id = %s AND NOT (origem_tabela = ANY(%s))
"""


def remover_sumidos(conexao, esquema_id, nomes_vistos):
    """Tira do catalogo o que nao apareceu numa varredura completa DESTE esquema.

    O filtro por esquema_id nao e detalhe: sem ele, mapear o schema B apagaria
    todos os objetos do schema A -- e a cascata levaria coluna, amostra,
    descricao_ia e os embeddings junto. Todo trabalho pago de IA, num DELETE.
    """
    lista = list(nomes_vistos)
    apagados = conexao.execute(SQL_REMOVER_OBJETOS, (esquema_id, lista)).fetchall()
    conexao.execute(SQL_REMOVER_RELACIONAMENTOS, (esquema_id, lista))
    conexao.commit()
    return [linha[0] for linha in apagados]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def filtrar_nomes(nomes, padroes):
    """Aceita os curingas do SQL ('PAC%') separados por virgula."""
    if not padroes:
        return nomes
    regras = [p.strip().upper().replace("%", "*") for p in padroes.split(",") if p.strip()]
    return [n for n in nomes if any(fnmatch.fnmatchcase(n.upper(), r) for r in regras)]


def restricao_gravavel(restricao, colunas_por_constraint, aresta_por_constraint):
    """Achata a constraint no formato de catalogo.restricao.

    O destino da FK vem da aresta ja resolvida; PK e UK simplesmente nao tem.
    """
    destino = aresta_por_constraint.get(restricao["nome"], {})
    chave = (restricao["owner"], restricao["nome"])
    return {
        "nome": restricao["nome"],
        "tipo": restricao["tipo"],
        "colunas": colunas_por_constraint.get(chave, []),
        "ref_schema": destino.get("destino_schema"),
        "ref_tabela": destino.get("destino_tabela"),
        "ref_colunas": destino.get("destino_colunas"),
        "delete_rule": restricao.get("delete_rule"),
        "status": restricao.get("status"),
    }


def conferir_env():
    """Mostra como o .env foi interpretado. Nao imprime a senha, so o formato.

    Existe porque erro de aspas em senha da o mesmo ORA-01017 que senha errada,
    e ai nao da para saber se o problema e o valor ou o jeito que ele foi lido.
    """
    def forma(valor):
        if valor is None:
            return "NAO DEFINIDA"
        if valor == "":
            return "vazia"
        detalhe = f"{len(valor)} caracteres"
        if valor[0] in "\"'" and valor[-1] == valor[0]:
            detalhe += f", ainda entre {valor[0]} {valor[0]} (identificador citado)"
        elif valor[0] in "\"'" or valor[-1] in "\"'":
            detalhe += ", com aspas soltas em uma ponta so -- provavelmente engano"
        if valor != valor.strip():
            detalhe += ", com espaco nas pontas"
        return detalhe

    print("Como o .env foi lido:\n")
    for chave in ("ORACLE_HOST", "ORACLE_PORT", "ORACLE_SERVICE", "ORACLE_SCHEMA",
                  "ORACLE_CLIENT_LIB_DIR", "POSTGRES_DSN"):
        print(f"  {chave:<22} = {os.environ.get(chave) or '(vazio)'}")

    # Usuario sai literal: a caixa e as aspas dele sao justamente o que se quer
    # conferir. Senha sai so descrita.
    usuario = os.environ.get("ORACLE_USER")
    print(f"  {'ORACLE_USER':<22} = {usuario!r}   [{forma(usuario)}]")
    print(f"  {'ORACLE_PASSWORD':<22} = <oculta>   [{forma(os.environ.get('ORACLE_PASSWORD'))}]")

    if usuario and usuario.startswith('"') and usuario.endswith('"'):
        print("\n  O usuario vai ao Oracle como identificador case-sensitive.")
    elif usuario:
        print(f"\n  O usuario vai sem aspas: o Oracle vai procurar por {usuario.upper()}.")
        print("  Para forcar as aspas ate o banco:  ORACLE_USER='\"meuUser\"'")

    conferir_rede(os.environ.get("ORACLE_HOST"), os.environ.get("ORACLE_PORT") or "1521")


def conferir_rede(host, porta, segundos=5):
    """Testa se da para abrir TCP no listener do Oracle a partir daqui.

    Rodando dentro do container, "daqui" e a rede do container: e esta a
    pergunta que importa, porque a rota da VPN do host pode ou nao chegar la.
    """
    if not host:
        return
    print()
    endereco = f"{host}:{porta}"
    conexao = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conexao.settimeout(segundos)
    try:
        conexao.connect((host, int(porta)))
        print(f"  rede: {endereco} respondeu -- da para mapear")
    except OSError as erro:
        print(f"  rede: {endereco} inalcancavel daqui ({erro})")
        print("        Ligue a VPN. Se ela ja estiver ligada, o que falta e a")
        print("        rota dela chegar ate a rede do container.")
    finally:
        conexao.close()


def montar_argumentos():
    p = argparse.ArgumentParser(
        description="Mapeia um schema Oracle para o catalogo de dados no Postgres."
    )
    p.add_argument("--schema", default=os.getenv("ORACLE_SCHEMA"), help="schema a mapear")
    p.add_argument("--tabelas", help="filtro por nome, com curinga: 'PAC%%,ATEND%%'")
    p.add_argument("--limite", type=int, help="processa so os N primeiros objetos (smoke test)")
    p.add_argument("--amostra", type=int, default=100, help="linhas por objeto (0 desliga)")
    p.add_argument("--somente-amostras", action="store_true",
                   help="refaz so a amostra, sem tocar em estrutura nem em IA")
    p.add_argument("--contagem-exata", action="store_true", help="COUNT(*) em vez de NUM_ROWS")
    p.add_argument("--sem-views", action="store_true", help="ignora as views do schema")
    p.add_argument("--timeout", type=float, default=60, help="limite por query, em segundos")
    p.add_argument("--pular-existentes", action="store_true", help="retoma sem refazer o gravado")
    p.add_argument("--mermaid", metavar="ARQUIVO", help="grava o diagrama ER em Mermaid")
    p.add_argument("--conferir-env", action="store_true",
                   help="mostra como o .env foi lido (sem a senha) e sai")
    p.add_argument("--somente-ddl", action="store_true",
                   help="aplica catalogo_schema.sql no Postgres e sai, sem tocar no Oracle")
    return p.parse_args()


def main():
    carregar_env(RAIZ / ".env")
    args = montar_argumentos()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    if args.conferir_env:
        conferir_env()
        return 0

    # Mudanca de schema nao devia exigir VPN: sem isto a unica forma de aplicar o
    # DDL seria um mapeamento inteiro, com o Oracle do outro lado da rede.
    if args.somente_ddl:
        dsn_pg = os.getenv("POSTGRES_DSN")
        if not dsn_pg:
            logger.error("faltou definir: POSTGRES_DSN")
            return 1
        aplicar_ddl(conectar_pg(dsn_pg))
        logger.info("schema aplicado em %s", ARQUIVO_DDL.name)
        return 0

    host = os.getenv("ORACLE_HOST")
    porta = os.getenv("ORACLE_PORT", "1521")
    service = os.getenv("ORACLE_SERVICE")
    usuario = os.getenv("ORACLE_USER")
    senha = os.getenv("ORACLE_PASSWORD")
    dsn_pg = os.getenv("POSTGRES_DSN")
    faltando = [
        nome
        for nome, valor in (
            ("ORACLE_HOST", host), ("ORACLE_SERVICE", service), ("ORACLE_USER", usuario),
            ("ORACLE_PASSWORD", senha), ("POSTGRES_DSN", dsn_pg), ("--schema", args.schema),
        )
        if not valor
    ]
    if faltando:
        logger.error("faltou definir: %s. Copie .env.example para .env e preencha.",
                     ", ".join(faltando))
        return 1

    if args.somente_amostras and args.amostra <= 0:
        logger.error("--somente-amostras com --amostra 0 so apagaria as amostras. "
                     "Se e isso que voce quer, faca pelo SQL.")
        return 1

    schema = args.schema.upper()

    pg = conectar_pg(dsn_pg)
    aplicar_ddl(pg)
    esquema_id = garantir_esquema(pg, "oracle", host, porta, service, schema)
    abrir_extracao(pg, schema, host, service, {
        "amostra": args.amostra, "somente_amostras": args.somente_amostras,
        "contagem_exata": args.contagem_exata, "tabelas": args.tabelas,
        "limite": args.limite, "sem_views": args.sem_views,
    })

    erros_globais = []
    status_final = "concluida"
    try:
        logger.info("conectando em %s:%s/%s como %s", host, porta, service, usuario)
        ora = conectar_oracle(host, porta, service, usuario, senha, args.timeout,
                              os.getenv("ORACLE_CLIENT_LIB_DIR"))
        cur = ora.cursor()
        cur.arraysize = 1000

        logger.info("lendo o dicionario do schema %s", schema)
        tabelas = ler_tabelas(cur, schema)
        info_tabela = {t["table_name"]: t for t in tabelas}
        views = [] if args.sem_views else ler_views(cur, schema)
        colunas_por_tabela, avisos = ler_colunas(cur, schema)
        erros_globais.extend(avisos)
        comentarios_tabela, comentarios_coluna = ler_comentarios(cur, schema)
        restricoes, colunas_por_constraint, tabela_por_constraint = ler_restricoes(cur, schema)
        indices_por_tabela = ler_indices(cur, schema)

        arestas, nao_resolvidas = resolver_relacionamentos(
            restricoes, colunas_por_constraint, tabela_por_constraint
        )
        if nao_resolvidas:
            amostra_fk = ", ".join(nao_resolvidas[:10])
            aviso = f"{len(nao_resolvidas)} FK sem destino resolvido: {amostra_fk}"
            logger.warning(aviso)
            erros_globais.append(aviso)

        arestas_por_tabela = {}
        for a in arestas:
            arestas_por_tabela.setdefault(a["origem_tabela"], []).append(a)
        aresta_por_constraint = {a["constraint_nome"]: a for a in arestas}

        pks = {}
        restricoes_por_tabela = {}
        for r in restricoes:
            restricoes_por_tabela.setdefault(r["tabela"], []).append(r)
            if r["tipo"] == "P":
                pks[r["tabela"]] = set(colunas_por_constraint.get((r["owner"], r["nome"]), []))

        nomes_tabelas = filtrar_nomes([t["table_name"] for t in tabelas], args.tabelas)
        alvos = [(n, "TABLE") for n in nomes_tabelas]
        alvos += [(n, "VIEW") for n in filtrar_nomes(views, args.tabelas)]
        if args.limite:
            alvos = alvos[: args.limite]

        ja_gravados = nomes_ja_gravados(pg, esquema_id) if args.pular_existentes else set()
        logger.info("%d objetos a processar (%d tabelas, %d views)",
                    len(alvos), len(tabelas), len(views))

        vistos = []
        for indice, (nome, tipo) in enumerate(alvos, start=1):
            vistos.append(nome)
            if nome in ja_gravados:
                logger.info("[%d/%d] %s  ja gravado, pulando", indice, len(alvos), nome)
                continue

            erros = []
            colunas = colunas_por_tabela.get(nome, [])
            chaves = pks.get(nome, set())
            for c in colunas:
                c["comentario"] = comentarios_coluna.get((nome, c["nome"]))
                c["eh_pk"] = c["nome"] in chaves

            info = info_tabela.get(nome, {})
            num_registros = info.get("num_rows")
            aproximada = True
            coletada_em = info.get("last_analyzed")
            if args.contagem_exata:
                try:
                    num_registros = contar_exato(cur, schema, nome)
                    aproximada = False
                    coletada_em = datetime.datetime.now()
                except Exception as erro:  # noqa: BLE001
                    erros.append(f"contagem: {erro}")

            amostra = []
            tem_registros = None
            amostra_falhou = False
            ordem = None
            if args.amostra > 0 and any(c.get("na_amostra") for c in colunas):
                ordem = escolher_ordem(
                    colunas, chaves, indices_por_tabela.get(nome, []), num_registros
                )
                try:
                    amostra = coletar_amostra(cur, schema, nome, colunas, args.amostra, ordem)
                    tem_registros = len(amostra) > 0
                except Exception as erro:  # noqa: BLE001
                    amostra_falhou = True
                    erros.append(f"amostra: {erro}")

            if args.somente_amostras:
                # Amostra que falhou nao apaga a que estava la: melhor a antiga do
                # que nenhuma, e o erro fica registrado no log.
                if amostra_falhou:
                    logger.warning("[%d/%d] %s  amostra falhou, mantendo a anterior: %s",
                                   indice, len(alvos), nome, erros[-1])
                    continue
                if not gravar_amostra(pg, esquema_id, nome, amostra):
                    logger.info("[%d/%d] %s  ainda nao esta no catalogo, pulando",
                                indice, len(alvos), nome)
                    continue
                logger.info("[%d/%d] %-30s %3d amostras  ordem: %s",
                            indice, len(alvos), nome, len(amostra), ordem or "nenhuma")
                continue

            view_sql = None
            if tipo == "VIEW":
                try:
                    view_sql = ler_sql_da_view(cur, schema, nome)
                except Exception as erro:  # noqa: BLE001
                    erros.append(f"texto da view: {erro}")

            objeto = {
                "esquema_id": esquema_id,
                "nome": nome,
                "tipo": tipo,
                "comentario": comentarios_tabela.get(nome),
                "num_registros": num_registros,
                "contagem_aproximada": aproximada,
                "contagem_coletada_em": coletada_em,
                "tem_registros": tem_registros,
                "particionada": info.get("partitioned") == "YES" if info else None,
                "view_sql": view_sql,
                "colunas": colunas,
                "restricoes": [
                    restricao_gravavel(r, colunas_por_constraint, aresta_por_constraint)
                    for r in restricoes_por_tabela.get(nome, [])
                ],
                "indices": indices_por_tabela.get(nome, []),
                "amostra": amostra,
                "erros": erros,
            }

            try:
                gravar_objeto(pg, objeto, arestas_por_tabela.get(nome, []))
            except Exception as erro:  # noqa: BLE001
                pg.rollback()
                logger.error("falha ao gravar %s: %s", nome, erro)
                erros_globais.append(f"{nome}: {erro}")
                continue

            logger.info(
                "[%d/%d] %-30s %10s reg  %2d colunas  %2d amostras  %d fk%s",
                indice, len(alvos), nome,
                f"{num_registros:,}".replace(",", ".") if num_registros is not None else "?",
                len(colunas), len(amostra), len(arestas_por_tabela.get(nome, [])),
                "  ERRO" if erros else "",
            )

        # So uma varredura completa pode concluir que o que sumiu do banco deve
        # sumir do catalogo; com filtro o "nao visto" nao significa nada. E
        # --somente-amostras nem olha estrutura: deixar passar aqui apagaria
        # objeto em cascata, levando junto descricao_ia e embedding.
        if not args.tabelas and not args.limite and not args.sem_views \
                and not args.somente_amostras:
            apagados = remover_sumidos(pg, esquema_id, vistos)
            if apagados:
                logger.info("removidos do catalogo (nao existem mais no schema): %s",
                            ", ".join(apagados))

        if args.mermaid:
            pathlib.Path(args.mermaid).write_text(gerar_mermaid(arestas), encoding="utf-8")
            logger.info("diagrama gravado em %s", args.mermaid)

        cur.close()
        ora.close()
    except Exception as erro:  # noqa: BLE001
        status_final = "falhou"
        erros_globais.append(str(erro))
        logger.exception("execucao interrompida")
        fechar_extracao(pg, status_final, erros_globais)
        pg.close()
        return 1

    fechar_extracao(pg, status_final, erros_globais)
    pg.close()
    logger.info("catalogo atualizado. Comece por: SELECT * FROM catalogo.vw_resumo;")
    return 0


if __name__ == "__main__":
    sys.exit(main())
