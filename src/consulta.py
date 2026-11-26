"""Assistente de consulta: SQL ao vivo no schema escolhido, com travas.

Fontes de dados > Assistente de consulta. Duas portas de entrada -- o SQL escrito
pelo usuario, ou um pedido em texto que a IA transforma em SQL lendo o dicionario
do catalogo -- e UMA porta de saida: executar(), que roda no Oracle da origem.

A sugestao da IA nunca executa sozinha: volta para o editor, e so roda quando o
usuario clica em Executar, passando pelas mesmas travas do SQL escrito a mao.

As travas sao camadas independentes; cada uma segura sozinha se a outra falhar:

1. validar(): checagem textual -- um statement, SELECT/WITH, sem escrita, sem
   PL/SQL, sem dblink, sem pacotes do sistema. Recusa antes de tocar no Oracle.
2. SET TRANSACTION READ ONLY: o proprio Oracle recusa DML (ORA-01456), mesmo que o
   usuario do cadastro tenha o grant.
3. Teto de linhas: a query vai embrulhada em ROWNUM <= 201, e o codigo faz UM
   fetchmany(201) e nada mais. LIMITE e constante -- nao vem da tela nem do ambiente.
4. call_timeout de 30s, celula cortada em 4.000 caracteres, no maximo 100 colunas.
5. Mascara: coluna com o nome de uma coluna marcada sensivel no schema sai como
   *****, e o valor real nao sai deste modulo.

Toda tentativa -- executada, recusada, com erro ou so sugerida -- vai para
catalogo.consulta_log. O resultado em si nunca e gravado nem logado.
"""

import datetime
import decimal
import logging
import re
import time

from pydantic import BaseModel

from . import busca, catalogo, ia, provedores, servidores

logger = logging.getLogger(__name__)

LIMITE = 200
TETO_SQL_BYTES = 20_000
TEMPO_MAXIMO_MS = 30_000
MAX_COLUNAS = 100
MAX_TEXTO = 4_000
MASCARA = "*****"

TABELAS_NO_CONTEXTO = 12


class ConsultaRecusada(Exception):
    """A checagem barrou o SQL. `motivo` diz a regra; `detalhe`, o trecho."""

    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


class ConsultaFalhou(Exception):
    """O Oracle (ou a conexao) recusou a query que passou pela checagem."""

    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


# --------------------------------------------------------------------------
# 1. Checagem textual (pura)
# --------------------------------------------------------------------------

# Verbos que nao tem lugar num SELECT. Comparados como PALAVRA inteira, entao uma
# coluna COMMENTS ou DELETED_AT passa; a coluna literalmente chamada DELETE nao.
PROIBIDAS = frozenset({
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "DROP", "ALTER", "CREATE", "TRUNCATE", "RENAME", "GRANT", "REVOKE", "COMMENT",
    "EXECUTE", "EXEC", "CALL", "BEGIN", "DECLARE", "LOCK",
    "COMMIT", "ROLLBACK", "SAVEPOINT",
    # SELECT ... INTO so existe em PL/SQL; INSERT INTO ja cai acima
    "INTO",
    # Tipos que buscam URL ou arquivo de dentro do banco (SSRF/XXE)
    "HTTPURITYPE", "DBURITYPE", "XDBURITYPE", "URIFACTORY", "XMLTYPE", "BFILENAME",
})

# Pacotes e visoes do sistema: fora do escopo de "consultar o schema escolhido"
PREFIXOS_PROIBIDOS = re.compile(
    r"\b(DBMS_\w*|UTL_\w*|DBA_\w*|CDB_\w*|G?V\$\w*|X\$\w*)",
)
DONOS_PROIBIDOS = re.compile(
    r"\b(SYS|SYSTEM|CTXSYS|XDB|MDSYS|ORDSYS|OUTLN|LBACSYS|WMSYS)\s*\.",
)
# PL/SQL inline do 12c: WITH FUNCTION f ... SELECT f(...)
PLSQL_INLINE = re.compile(r"\bWITH\s+(FUNCTION|PROCEDURE)\b")
PALAVRA = re.compile(r"[A-Z_][A-Z0-9_$#]*")

# Delimitadores do q-quote do Oracle: q'[...]', q'{...}', q'<...>', q'(...)', q'!...!'
_FECHA_Q = {"[": "]", "{": "}", "<": ">", "(": ")"}


def _varrer(sql):
    """Separa o SQL em duas versoes, numa passada so:

    - `analise`: sem comentarios e com cada literal de texto trocado por '?', para
      a checagem nao se enganar com DELETE dentro de uma string nem deixar passar
      um DROP escondido num comentario;
    - `executavel`: sem comentarios, com os literais intactos -- e o que vai ao banco.

    Identificador entre aspas duplas perde as aspas na analise ("SYS"."X" tem de
    cair na mesma regra de SYS.X) e fica intacto no executavel.
    """
    analise, executavel = [], []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        par = sql[i:i + 2]
        if par == "--":
            fim = sql.find("\n", i)
            i = n if fim < 0 else fim
            analise.append(" ")
            executavel.append(" ")
            continue
        if par == "/*":
            fim = sql.find("*/", i + 2)
            if fim < 0:
                raise ConsultaRecusada("Comentário /* sem fechamento")
            i = fim + 2
            analise.append(" ")
            executavel.append(" ")
            continue
        # q'X...X' e nq'X...X'
        prefixo_q = re.match(r"[nN]?[qQ]'(.)", sql[i:i + 4])
        if prefixo_q and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] in "_$#")):
            abre = prefixo_q.group(1)
            fecha = _FECHA_Q.get(abre, abre) + "'"
            inicio = i + prefixo_q.end()
            fim = sql.find(fecha, inicio)
            if fim < 0:
                raise ConsultaRecusada("Literal q'…' sem fechamento")
            executavel.append(sql[i:fim + 2])
            analise.append("'?'")
            i = fim + 2
            continue
        if c == "'":
            j = i + 1
            while True:
                j = sql.find("'", j)
                if j < 0:
                    raise ConsultaRecusada("Texto entre aspas sem fechamento")
                if sql[j + 1:j + 2] == "'":  # '' escapado
                    j += 2
                    continue
                break
            executavel.append(sql[i:j + 1])
            analise.append("'?'")
            i = j + 1
            continue
        if c == '"':
            j = sql.find('"', i + 1)
            if j < 0:
                raise ConsultaRecusada("Identificador entre aspas sem fechamento")
            executavel.append(sql[i:j + 1])
            analise.append(sql[i + 1:j])
            i = j + 1
            continue
        analise.append(c)
        executavel.append(c)
        i += 1
    return "".join(analise), "".join(executavel)


def validar(sql):
    """Devolve o SQL pronto para executar, ou levanta ConsultaRecusada."""
    sql = sql or ""
    if len(sql.encode("utf-8")) > TETO_SQL_BYTES:
        raise ConsultaRecusada(
            "Consulta grande demais", f"O limite é {TETO_SQL_BYTES // 1000} KB de texto."
        )
    analise, executavel = _varrer(sql)
    analise = analise.strip().upper()
    executavel = executavel.strip()

    # Um ; no fim e costume, nao um segundo statement
    if analise.endswith(";"):
        analise = analise[:-1].rstrip()
        executavel = executavel[:executavel.rfind(";")].rstrip()
    if not analise:
        raise ConsultaRecusada("Escreva uma consulta")
    if ";" in analise:
        raise ConsultaRecusada(
            "Uma consulta por vez", "Há mais de um comando separado por ponto e vírgula."
        )

    primeira = PALAVRA.search(analise.lstrip("( \n\t\r"))
    if not primeira or primeira.start() != 0 or primeira.group() not in ("SELECT", "WITH"):
        raise ConsultaRecusada(
            "Só consultas de leitura", "A consulta tem de começar com SELECT ou WITH."
        )

    if PLSQL_INLINE.search(analise):
        raise ConsultaRecusada("PL/SQL não é permitido", "WITH FUNCTION/PROCEDURE.")

    proibidas = sorted({p for p in PALAVRA.findall(analise) if p in PROIBIDAS})
    if proibidas:
        raise ConsultaRecusada(
            "Comando não permitido numa consulta", f"Encontrado: {', '.join(proibidas)}."
        )

    if "@" in analise:
        raise ConsultaRecusada("Database link não é permitido", "A consulta usa @.")

    sistema = PREFIXOS_PROIBIDOS.search(analise) or DONOS_PROIBIDOS.search(analise)
    if sistema:
        raise ConsultaRecusada(
            "Objetos do sistema estão fora do escopo",
            f"Encontrado: {sistema.group(0).rstrip('. ')}. Consulte só o schema escolhido.",
        )
    return executavel


def embrulhar(sql):
    """O teto no proprio banco: o Oracle para de produzir linha na 201a."""
    return f"SELECT * FROM (\n{sql}\n) WHERE ROWNUM <= {LIMITE + 1}"


# --------------------------------------------------------------------------
# 2. Leitura do resultado (pura sobre um cursor)
# --------------------------------------------------------------------------


def celula(valor):
    """Valor do Oracle -> algo que a tela mostra sem estourar memoria nem HTML."""
    if valor is None or isinstance(valor, (bool, int, float, decimal.Decimal)):
        return valor
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor
    if isinstance(valor, (bytes, bytearray)):
        return f"‹binário {len(valor)} bytes›"
    if hasattr(valor, "read"):  # LOB: le so o comeco, nunca o objeto inteiro
        tipo = str(getattr(valor, "type", ""))
        if "BLOB" in tipo or "BFILE" in tipo:
            return f"‹binário {valor.size()} bytes›"
        tamanho = valor.size()
        texto = valor.read(1, MAX_TEXTO) if tamanho else ""
        return texto + ("…" if tamanho > MAX_TEXTO else "")
    texto = str(valor)
    return texto if len(texto) <= MAX_TEXTO else texto[:MAX_TEXTO] + "…"


def ler(cursor, sensiveis=frozenset()):
    """UM fetchmany(LIMITE + 1) e nada mais: o teto nao depende do SQL.

    Devolve (colunas, linhas, truncada, mascaradas). A linha 201 so existe para
    saber se houve corte; nunca chega a quem chamou.
    """
    nomes = [d[0] for d in (cursor.description or [])]
    if len(nomes) > MAX_COLUNAS:
        raise ConsultaFalhou(
            f"A consulta devolve {len(nomes)} colunas",
            f"O limite é {MAX_COLUNAS}: escolha as colunas em vez de SELECT *.",
        )
    brutas = cursor.fetchmany(LIMITE + 1)
    truncada = len(brutas) > LIMITE
    mascarar = [nome.upper() in sensiveis for nome in nomes]
    linhas = [
        [MASCARA if mascarar[k] and v is not None else celula(v) for k, v in enumerate(linha)]
        for linha in brutas[:LIMITE]
    ]
    mascaradas = [nome for nome, m in zip(nomes, mascarar) if m]
    return nomes, linhas, truncada, mascaradas


# --------------------------------------------------------------------------
# 3. Execucao na origem
# --------------------------------------------------------------------------

SCHEMA_VALIDO = re.compile(r"^[A-Z][A-Z0-9_$#]*$")

SQL_SENSIVEIS = """
SELECT DISTINCT upper(c.nome) AS nome
  FROM catalogo.coluna c JOIN catalogo.objeto o ON o.id = c.objeto_id
 WHERE o.esquema_id = %s AND c.sensivel
"""

SQL_COBERTURA = """
SELECT count(*) FILTER (WHERE c.sensivel IS NULL) AS sem_avaliacao,
       count(*)                                   AS colunas
  FROM catalogo.coluna c JOIN catalogo.objeto o ON o.id = c.objeto_id
 WHERE o.esquema_id = %s
"""


def sensiveis(esquema_id):
    linhas = catalogo.consultar(SQL_SENSIVEIS, (esquema_id,), "colunas sensíveis do schema")
    return frozenset(linha["nome"] for linha in linhas)


def cobertura(esquema_id):
    """Quantas colunas do schema ainda nao passaram pela avaliacao de sensibilidade."""
    return catalogo.um(SQL_COBERTURA, (esquema_id,), "cobertura da máscara")


def _codigo_ora(erro):
    args = getattr(erro, "args", ())
    return getattr(args[0], "code", None) if args else None


def rodar(conexao, schema, sql, sensiveis_=frozenset()):
    """A sequencia na conexao aberta. Separada de executar() para o teste usar
    uma conexao falsa e conferir a ORDEM: schema, READ ONLY, query, rollback."""
    if not SCHEMA_VALIDO.match(schema):
        raise ConsultaFalhou("Nome de schema inválido no cadastro", schema)
    conexao.call_timeout = TEMPO_MAXIMO_MS
    cursor = conexao.cursor()
    try:
        cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {schema}")
        # Primeiro statement da transacao: dai em diante o Oracle recusa DML
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.arraysize = LIMITE + 1
        cursor.prefetchrows = LIMITE + 1
        try:
            cursor.execute(embrulhar(sql))
        except Exception as erro:  # noqa: BLE001 - so o 918 tem tratamento
            # ORA-00918: o SELECT * de fora nao aceita duas colunas de mesmo nome
            # (a.ID, b.ID num join). Roda a query crua: o fetchmany unico continua
            # sendo o teto, e a transacao segue READ ONLY.
            if _codigo_ora(erro) != 918:
                raise
            cursor.execute(sql)
        return ler(cursor, sensiveis_)
    finally:
        try:
            conexao.rollback()
        finally:
            cursor.close()


def executar(esquema_id, sql_digitado, usuario=None, modo="sql", prompt=None, origem_ia=None):
    """Checa, roda e audita. Devolve o resultado para a tela.

    Levanta ConsultaRecusada (checagem) ou ConsultaFalhou (conexao/Oracle) -- as
    duas ja auditadas.
    """
    registro = {"esquema_id": esquema_id, "usuario": usuario, "modo": modo,
                "prompt": prompt, "sql": sql_digitado, **(origem_ia or {})}
    try:
        sql = validar(sql_digitado)
    except ConsultaRecusada as falha:
        auditar(**registro, status="recusada", erro=f"{falha.motivo}. {falha.detalhe}")
        raise

    import oracledb

    inicio = time.perf_counter()
    conexao = None
    try:
        origem = servidores.origem_do_esquema(esquema_id)
        conexao = oracledb.connect(
            user=origem["usuario"], password=origem["senha"],
            dsn=f"{origem['host']}:{origem['porta']}/{origem['service']}",
            tcp_connect_timeout=servidores.TIMEOUT,
        )
        colunas, linhas, truncada, mascaradas = rodar(
            conexao, origem["schema"], sql, sensiveis(esquema_id)
        )
    except (ConsultaFalhou, servidores.ConfiguracaoInvalida) as falha:
        auditar(**registro, status="erro", erro=f"{falha.motivo}. {falha.detalhe}",
                ms=_ms(inicio))
        raise ConsultaFalhou(falha.motivo, falha.detalhe) from falha
    except Exception as erro:  # noqa: BLE001 - erro do Oracle vira mensagem na tela
        mensagem = str(erro).strip().splitlines()[0] if str(erro).strip() else type(erro).__name__
        auditar(**registro, status="erro", erro=mensagem, ms=_ms(inicio))
        raise ConsultaFalhou("O Oracle recusou a consulta", mensagem) from erro
    finally:
        if conexao is not None:
            conexao.close()

    ms = _ms(inicio)
    auditar(**registro, status="ok", linhas=len(linhas), truncada=truncada, ms=ms)
    logger.info("consulta de %s no schema %s: %s linhas%s em %s ms",
                usuario or "anônimo", esquema_id, len(linhas),
                " (truncada)" if truncada else "", ms)
    return {"colunas": colunas, "linhas": linhas, "truncada": truncada,
            "mascaradas": mascaradas, "ms": ms, "sql": sql}


def _ms(inicio):
    return round((time.perf_counter() - inicio) * 1000)


# --------------------------------------------------------------------------
# Auditoria
# --------------------------------------------------------------------------

SQL_AUDITAR = """
INSERT INTO catalogo.consulta_log
    (esquema_id, usuario, modo, prompt, sql, status, linhas, truncada, ms, erro,
     provedor, modelo)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def auditar(esquema_id, usuario, modo, status, prompt=None, sql=None, linhas=None,
            truncada=None, ms=None, erro=None, provedor=None, modelo=None):
    """Grava a tentativa. Falha da auditoria vai para o log, mas nao derruba a tela."""
    try:
        catalogo.executar(
            SQL_AUDITAR,
            (esquema_id, usuario, modo, prompt, (sql or "")[:TETO_SQL_BYTES], status,
             linhas, truncada, ms, (erro or "")[:2000] or None, provedor, modelo),
            "auditoria da consulta",
        )
    except catalogo.ConsultaFalhou as falha:
        logger.error("auditoria da consulta NAO gravada (%s, %s): %s",
                     usuario, status, falha)


def historico(usuario, limite=20):
    return catalogo.consultar(
        f"""SELECT l.id, l.modo, l.prompt, l.sql, l.status, l.linhas, l.truncada, l.ms,
                   l.erro, l.criado_em, e.nome AS esquema
              FROM catalogo.consulta_log l
              LEFT JOIN catalogo.esquema e ON e.id = l.esquema_id
             WHERE l.usuario IS NOT DISTINCT FROM %s
             ORDER BY l.criado_em DESC LIMIT {int(limite)}""",
        (usuario,), "histórico de consultas",
    )


def buscar_log(log_id, usuario):
    """Uma entrada do historico -- so do proprio usuario."""
    return catalogo.um(
        "SELECT * FROM catalogo.consulta_log WHERE id = %s AND usuario IS NOT DISTINCT FROM %s",
        (log_id, usuario), "consulta do histórico",
    )


# --------------------------------------------------------------------------
# 4. Sugestao por IA
# --------------------------------------------------------------------------

INSTRUCOES_CONSULTA = """Você escreve SQL para Oracle a partir de um pedido em \
português e do dicionário de dados de UM schema.

Regras:
- Responda com UMA consulta de leitura: começa com SELECT ou WITH. Nunca INSERT, \
UPDATE, DELETE, MERGE, DDL, PL/SQL, SELECT INTO, FOR UPDATE ou database link.
- Use SOMENTE as tabelas e colunas listadas no contexto. Não invente nomes. Se o \
pedido precisa de algo que não está no contexto, diga isso em "premissas" e faça o \
melhor com o que existe.
- Não prefixe tabelas com o nome do schema: a sessão já aponta para ele.
- Use as FKs listadas para os JOINs. Dê alias às colunas de mesmo nome vindas de \
tabelas diferentes.
- O resultado é cortado em 200 linhas de qualquer forma; ordene para que as \
linhas mais relevantes venham primeiro.
- Dialeto Oracle: datas com TRUNC/ADD_MONTHS/SYSDATE, texto com UPPER/LIKE, \
FETCH FIRST n ROWS ONLY é aceito.
- "explicacao": em português, 2 a 4 frases sobre o que a consulta faz.
- "tabelas_usadas": os nomes das tabelas do contexto que a consulta usa.
- "premissas": suposições que você fez sobre o pedido ou os dados (pode ser vazio).
"""


class Sugestao(BaseModel):
    sql: str
    explicacao: str
    tabelas_usadas: list[str]
    premissas: list[str]


SQL_OBJETOS = """
SELECT o.id, o.nome, o.tipo, o.num_registros, d.rotulo, d.resumo
  FROM catalogo.objeto o
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 WHERE o.esquema_id = %s AND upper(o.nome) = ANY(%s)
"""

SQL_LEXICAL = """
SELECT o.nome
  FROM catalogo.objeto o
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 WHERE o.esquema_id = %s
   AND (o.nome ILIKE ANY(%s) OR d.rotulo ILIKE ANY(%s) OR d.resumo ILIKE ANY(%s))
 ORDER BY o.num_registros DESC NULLS LAST
 LIMIT %s
"""

SQL_COLUNAS_CONTEXTO = """
SELECT nome, tipo_completo, eh_pk, aceita_nulo, descricao_ia
  FROM catalogo.coluna WHERE objeto_id = %s ORDER BY posicao
"""


def nomes_digitados(texto):
    """'CAPPAYMENT, capbudget  X' -> ['CAPPAYMENT', 'CAPBUDGET', 'X'] sem repetir."""
    vistos = []
    for nome in re.split(r"[\s,;]+", (texto or "").upper()):
        if nome and nome not in vistos:
            vistos.append(nome)
    return vistos


def tabelas_relevantes(esquema_id, pedido, limite=TABELAS_NO_CONTEXTO):
    """Nomes das tabelas que o pedido parece pedir. Semantica quando ha vetores;
    senao, casamento por palavra no nome e na descricao."""
    try:
        linhas, _ = busca.buscar(pedido, esquema_id, escopo="tabelas", topk=limite)
        nomes = [linha["nome"] for linha in linhas]
        if nomes:
            return nomes, "semântica"
    except Exception as erro:  # noqa: BLE001 - sem embedding a busca lexical resolve
        logger.info("assistente: busca semântica indisponível (%s); usando lexical", erro)

    padroes = [f"%{busca.escapar_like(t)}%" for t in busca.tokens(pedido)]
    if not padroes:
        return [], "lexical"
    linhas = catalogo.consultar(
        SQL_LEXICAL, (esquema_id, padroes, padroes, padroes, limite), "tabelas por palavra"
    )
    return [linha["nome"] for linha in linhas], "lexical"


def carregar_contexto(esquema_id, nomes):
    """Metadado de cada tabela, na ordem dada. Nome que nao existe fica de fora."""
    if not nomes:
        return []
    linhas = catalogo.consultar(
        SQL_OBJETOS, (esquema_id, [n.upper() for n in nomes]), "tabelas do contexto"
    )
    por_nome = {linha["nome"].upper(): linha for linha in linhas}
    tabelas = []
    for nome in nomes:
        objeto = por_nome.get(nome.upper())
        if not objeto or objeto in tabelas:
            continue
        objeto["colunas"] = catalogo.consultar(
            SQL_COLUNAS_CONTEXTO, (objeto["id"],), f"colunas de {objeto['nome']}"
        )
        objeto["fks"] = catalogo.consultar(
            ia.SQL_FKS, (objeto["nome"], esquema_id), f"FKs de {objeto['nome']}"
        )
        tabelas.append(objeto)
    return tabelas


def _bloco_tabela(t):
    linhas = [f"## {t['nome']} ({t['tipo']}, ~{t['num_registros'] or 0} linhas)"]
    if t.get("rotulo") or t.get("resumo"):
        linhas.append(f"{t.get('rotulo') or ''} — {t.get('resumo') or ''}".strip(" —"))
    for c in t["colunas"]:
        marcas = " PK" if c["eh_pk"] else ""
        marcas += "" if c["aceita_nulo"] else " NOT NULL"
        descricao = (c.get("descricao_ia") or "")[:160]
        linhas.append(f"- {c['nome']} {c['tipo_completo']}{marcas}"
                      + (f": {descricao}" if descricao else ""))
    for fk in t["fks"]:
        linhas.append(f"FK ({fk['colunas']}) -> {fk['destino_tabela']}({fk['destino_colunas']})")
    return "\n".join(linhas)


def montar_contexto(pedido, tabelas, teto=None):
    """Pedido + dicionario das tabelas, dentro do teto. SO metadado: nenhuma linha
    de amostra nem valor real vai para o provedor de IA.

    Devolve (texto, nomes que couberam).
    """
    teto = teto or ia.TETO_PROMPT_BYTES
    cabeca = f"Pedido do usuário:\n{pedido.strip()}\n\nDicionário das tabelas disponíveis:\n"
    partes, usados = [cabeca], []
    tamanho = len(cabeca.encode("utf-8"))
    for t in tabelas:
        bloco = _bloco_tabela(t) + "\n\n"
        peso = len(bloco.encode("utf-8"))
        if tamanho + peso > teto:
            continue
        partes.append(bloco)
        usados.append(t["nome"])
        tamanho += peso
    return "".join(partes), usados


def sugerir(esquema_id, pedido, par=None, tabelas_extra="", usuario=None):
    """Chama a IA e devolve a sugestao para o editor. NAO executa nada."""
    if not (pedido or "").strip():
        raise ConsultaRecusada("Descreva o que você quer consultar")
    extras = nomes_digitados(tabelas_extra)
    relevantes, via = tabelas_relevantes(esquema_id, pedido)
    nomes = extras + [n for n in relevantes if n.upper() not in extras]
    tabelas = carregar_contexto(esquema_id, nomes)
    if not tabelas:
        raise ConsultaRecusada(
            "Não achamos tabelas para esse pedido",
            "Cite as tabelas no campo “Tabelas”, ou use palavras do nome delas.",
        )
    payload, usados = montar_contexto(pedido, tabelas)

    prov = provedores.escolher(par)
    logger.info("assistente: sugerindo SQL via %s/%s com %s tabelas (%s), %s bytes",
                prov.slug, prov.modelo, len(usados), via, len(payload))
    sugestao, truncou, entrada, saida = ia._chamar_com_retentativa(
        prov, payload, len(usados),
        instrucoes=INSTRUCOES_CONSULTA, modelo=Sugestao, esquema_nome="sugestao_sql",
    )
    if truncou:
        raise ia.GeracaoFalhou("A resposta não coube no limite de tokens",
                               "Simplifique o pedido ou cite menos tabelas.")

    avisos = []
    fora = [t for t in sugestao.tabelas_usadas if t.upper() not in {u.upper() for u in usados}]
    if fora:
        avisos.append(f"A IA citou tabelas fora do contexto: {', '.join(fora)}.")
    try:
        validar(sugestao.sql)
    except ConsultaRecusada as falha:
        avisos.append(f"A sugestão não passa na checagem: {falha.motivo}. {falha.detalhe}")

    auditar(esquema_id, usuario, "prompt", "sugerida", prompt=pedido, sql=sugestao.sql,
            provedor=prov.slug, modelo=prov.modelo)
    return {
        "sql": sugestao.sql.strip(),
        "explicacao": sugestao.explicacao,
        "premissas": sugestao.premissas,
        "tabelas": usados,
        "via": via,
        "avisos": avisos,
        "provedor": prov.slug,
        "modelo": prov.modelo,
        "tokens_entrada": entrada,
        "tokens_saida": saida,
    }
