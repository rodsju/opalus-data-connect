"""Testes do que roda sem banco nenhum.

E justamente a parte que nao da para validar sem VPN: conversao de valor para
jsonb, escolha da ordem, montagem do SELECT da amostra e resolucao de FK. Os
drivers (oracledb, psycopg) sao importados sob demanda pelo script, entao este
arquivo roda mesmo sem eles instalados.
"""

import datetime
import decimal
import importlib.util
import pathlib

import pytest

CAMINHO = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "mapear_oracle.py"
_spec = importlib.util.spec_from_file_location("mapear_oracle", CAMINHO)
mo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mo)


# ---------------------------------------------------------------------------
# Conversao para jsonb
# ---------------------------------------------------------------------------


def test_converter_decimal_integral_vira_int():
    assert mo.converter_valor(decimal.Decimal("42")) == 42
    assert isinstance(mo.converter_valor(decimal.Decimal("42")), int)


def test_converter_decimal_fracionario_vira_float():
    assert mo.converter_valor(decimal.Decimal("1.5")) == 1.5


def test_converter_datas_viram_iso():
    assert mo.converter_valor(datetime.datetime(2024, 7, 19, 8, 30)) == "2024-07-19T08:30:00"
    assert mo.converter_valor(datetime.date(2024, 7, 19)) == "2024-07-19"


def test_converter_binario_vira_marcador():
    assert mo.converter_valor(b"\x00\x01\x02") == "<BINARIO 3 bytes>"


def test_converter_texto_longo_e_truncado():
    saida = mo.converter_valor("a" * 900)
    assert saida.startswith("a" * mo.LIMITE_TEXTO)
    assert "truncado, 900 caracteres" in saida


def test_converter_preserva_nulo_e_bool():
    assert mo.converter_valor(None) is None
    assert mo.converter_valor(True) is True


# ---------------------------------------------------------------------------
# SELECT da amostra
# ---------------------------------------------------------------------------


def coluna(nome, tipo, tipo_owner=None):
    c = {"nome": nome, "tipo": tipo, "tipo_owner": tipo_owner, "tamanho": None,
         "precisao": None, "escala": None, "char_length": None, "char_used": None}
    c["na_amostra"] = mo.entra_na_amostra(c)
    return c


def test_select_da_amostra_pula_tipos_pesados():
    """LONG quebra o fetch e tipo de objeto do usuario nao vira texto; BLOB fica."""
    colunas = [
        coluna("CD_PACIENTE", "NUMBER"),
        coluna("LAUDO", "LONG"),
        coluna("GEO", "SDO_GEOMETRY", tipo_owner="MDSYS"),
        coluna("NM_PACIENTE", "VARCHAR2"),
    ]
    sql, nomes = mo.montar_select_amostra("DBIWGERIATRICS", "PACIENTE", colunas, 100)
    assert nomes == ["CD_PACIENTE", "NM_PACIENTE"]
    assert sql == (
        'SELECT * FROM (SELECT "CD_PACIENTE", "NM_PACIENTE" '
        'FROM "DBIWGERIATRICS"."PACIENTE") WHERE ROWNUM <= 100'
    )


def test_select_da_amostra_ordenada():
    colunas = [coluna("ID", "NUMBER"), coluna("NOME", "VARCHAR2")]
    sql, _ = mo.montar_select_amostra("S", "T", colunas, 100, "ID")
    assert sql == (
        'SELECT * FROM (SELECT "ID", "NOME" FROM "S"."T" ORDER BY "ID" DESC) '
        "WHERE ROWNUM <= 100"
    )


def test_rownum_fica_fora_do_subselect():
    """O teste que impede o bug voltar sem ninguem ver.

    No Oracle o ROWNUM e atribuido ANTES do ORDER BY. Se o limite migrar para
    dentro do subselect, a query volta a pegar as primeiras linhas fisicas e so
    ordenar essas -- continua devolvendo 100 linhas, e ninguem percebe que sao as
    antigas de novo.
    """
    colunas = [coluna("ID", "NUMBER")]
    sql, _ = mo.montar_select_amostra("S", "T", colunas, 100, "ID")
    interno = sql[sql.index("(") + 1 : sql.rindex(")")]
    assert "ORDER BY" in interno
    assert "ROWNUM" not in interno
    assert sql.rindex(")") < sql.index("ROWNUM")


def test_select_da_amostra_resume_o_blob():
    """BLOB nao vem inteiro: o Oracle monta o resumo, uma coluna de saida so."""
    sql, nomes = mo.montar_select_amostra("S", "T", [coluna("FOTO", "BLOB")], 100)
    assert nomes == ["FOTO"]
    assert "DBMS_LOB.GETLENGTH(\"FOTO\")" in sql
    assert "RAWTOHEX(DBMS_LOB.SUBSTR(\"FOTO\", 16, 1))" in sql
    assert sql.count("AS \"FOTO\"") == 1


def test_select_da_amostra_sem_coluna_usavel():
    sql, nomes = mo.montar_select_amostra("S", "T", [coluna("LAUDO", "LONG")], 100)
    assert sql is None and nomes == []


# ---------------------------------------------------------------------------
# Escolha da ordem: quais tabelas dao para pegar pelo mais recente
# ---------------------------------------------------------------------------

def test_ordem_prefere_pk_numerica():
    """O caminho barato: o indice da PK sempre existe, entao nem tabela de 341
    milhoes de linhas custa caro."""
    colunas = [coluna("ID", "NUMBER"), coluna("CREATIONDATE", "DATE")]
    assert mo.escolher_ordem(colunas, {"ID"}, [], 341_000_000) == "ID"


def test_ordem_ignora_pk_nao_numerica_e_composta():
    colunas = [coluna("CODIGO", "VARCHAR2"), coluna("CREATIONDATE", "DATE")]
    assert mo.escolher_ordem(colunas, {"CODIGO"}, [], 10) == "CREATIONDATE"
    colunas = [coluna("A", "NUMBER"), coluna("B", "NUMBER")]
    assert mo.escolher_ordem(colunas, {"A", "B"}, [], 10) is None


def test_ordem_usa_data_que_lidera_indice_mesmo_em_tabela_grande():
    colunas = [coluna("EVENTDATE", "DATE")]
    indices = [{"colunas": ["EVENTDATE", "ID"]}]
    assert mo.escolher_ordem(colunas, set(), indices, 5_000_000) == "EVENTDATE"


def test_ordem_nao_indexada_so_em_tabela_pequena():
    """Aqui o sort acontece de verdade -- e por isso tem teto."""
    colunas = [coluna("EVENTDATE", "DATE")]
    assert mo.escolher_ordem(colunas, set(), [], 50_000) == "EVENTDATE"
    assert mo.escolher_ordem(colunas, set(), [], 5_000_000) is None


def test_ordem_de_view_nao_ordena():
    """View nao tem PK nem indice, e num_registros vem None de ALL_TABLES."""
    colunas = [coluna("EVENTDATE", "DATE")]
    assert mo.escolher_ordem(colunas, set(), [], None) is None


def test_ordem_sem_sinal_nenhum():
    colunas = [coluna("DESCRICAO", "VARCHAR2")]
    assert mo.escolher_ordem(colunas, set(), [], 10) is None


def test_ordem_escolhe_a_data_preferida():
    colunas = [coluna("ENDDATE", "DATE"), coluna("CREATIONDATE", "DATE"),
               coluna("EVENTDATE", "DATE")]
    assert mo.escolher_ordem(colunas, set(), [], 10) == "CREATIONDATE"


def test_citar_dobra_aspas_internas():
    assert mo.citar('ES"TRANHO') == '"ES""TRANHO"'


# ---------------------------------------------------------------------------
# Escopo por esquema -- o SQL que apaga
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sql", [mo.SQL_REMOVER_OBJETOS, mo.SQL_REMOVER_RELACIONAMENTOS]
)
def test_remover_sumidos_e_escopado_por_esquema(sql):
    """A guarda mais importante do arquivo.

    Sem `esquema_id` no WHERE, mapear um segundo schema apaga os objetos do
    primeiro, e a cascata leva coluna, amostra, descricao_ia e os embeddings --
    todo o trabalho pago de IA, num DELETE que nao avisa.
    """
    assert "esquema_id = %s" in sql
    assert "DELETE" in sql


def test_remover_sumidos_devolve_o_que_apagou():
    """Sem o RETURNING o log nao consegue dizer o que sumiu."""
    assert "RETURNING nome" in mo.SQL_REMOVER_OBJETOS


# ---------------------------------------------------------------------------
# Tipo completo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "col,esperado",
    [
        ({"tipo": "NUMBER", "precisao": 10, "escala": 0}, "NUMBER(10)"),
        ({"tipo": "NUMBER", "precisao": 10, "escala": 2}, "NUMBER(10,2)"),
        ({"tipo": "NUMBER", "precisao": None, "escala": None}, "NUMBER"),
        ({"tipo": "VARCHAR2", "char_length": 60, "char_used": "C"}, "VARCHAR2(60 CHAR)"),
        ({"tipo": "VARCHAR2", "char_length": 60, "char_used": "B"}, "VARCHAR2(60 BYTE)"),
        ({"tipo": "DATE"}, "DATE"),
        ({"tipo": "TIMESTAMP(6)"}, "TIMESTAMP(6)"),
        ({"tipo": "RAW", "tamanho": 16}, "RAW(16)"),
    ],
)
def test_tipo_completo(col, esperado):
    assert mo.tipo_completo(col) == esperado


# ---------------------------------------------------------------------------
# Resolucao de FK
# ---------------------------------------------------------------------------


def test_resolver_relacionamentos_monta_a_aresta():
    restricoes = [
        {"owner": "DBIWGERIATRICS", "nome": "PK_PACIENTE", "tipo": "P",
         "tabela": "PACIENTE", "ref_owner": None, "ref_constraint": None,
         "delete_rule": None, "status": "ENABLED"},
        {"owner": "DBIWGERIATRICS", "nome": "FK_ATEND_PAC", "tipo": "R",
         "tabela": "ATENDIMENTO", "ref_owner": "DBIWGERIATRICS",
         "ref_constraint": "PK_PACIENTE", "delete_rule": "CASCADE", "status": "ENABLED"},
    ]
    colunas = {
        ("DBIWGERIATRICS", "PK_PACIENTE"): ["CD_PACIENTE"],
        ("DBIWGERIATRICS", "FK_ATEND_PAC"): ["CD_PACIENTE"],
    }
    tabelas = {
        ("DBIWGERIATRICS", "PK_PACIENTE"): "PACIENTE",
        ("DBIWGERIATRICS", "FK_ATEND_PAC"): "ATENDIMENTO",
    }

    arestas, nao_resolvidas = mo.resolver_relacionamentos(restricoes, colunas, tabelas)

    assert nao_resolvidas == []
    assert arestas == [
        {
            "constraint_nome": "FK_ATEND_PAC",
            "origem_tabela": "ATENDIMENTO",
            "origem_colunas": ["CD_PACIENTE"],
            "destino_schema": "DBIWGERIATRICS",
            "destino_tabela": "PACIENTE",
            "destino_colunas": ["CD_PACIENTE"],
            "delete_rule": "CASCADE",
        }
    ]


def test_fk_para_schema_externo_e_resolvida():
    restricoes = [
        {"owner": "DBIWGERIATRICS", "nome": "FK_EXTERNA", "tipo": "R",
         "tabela": "ATENDIMENTO", "ref_owner": "OUTRO_SCHEMA",
         "ref_constraint": "PK_CONV", "delete_rule": None, "status": "ENABLED"},
    ]
    colunas = {
        ("DBIWGERIATRICS", "FK_EXTERNA"): ["CD_CONVENIO"],
        ("OUTRO_SCHEMA", "PK_CONV"): ["CD_CONVENIO"],
    }
    tabelas = {("OUTRO_SCHEMA", "PK_CONV"): "CONVENIO"}

    arestas, nao_resolvidas = mo.resolver_relacionamentos(restricoes, colunas, tabelas)

    assert nao_resolvidas == []
    assert arestas[0]["destino_schema"] == "OUTRO_SCHEMA"
    assert arestas[0]["destino_tabela"] == "CONVENIO"


def test_fk_sem_destino_conhecido_nao_vira_aresta():
    restricoes = [
        {"owner": "DBIWGERIATRICS", "nome": "FK_ORFA", "tipo": "R",
         "tabela": "ATENDIMENTO", "ref_owner": "SUMIDO", "ref_constraint": "PK_X",
         "delete_rule": None, "status": "ENABLED"},
    ]
    arestas, nao_resolvidas = mo.resolver_relacionamentos(restricoes, {}, {})
    assert arestas == []
    assert nao_resolvidas == ["FK_ORFA"]


def test_mermaid_sai_do_grafo():
    arestas = [
        {"constraint_nome": "FK_ATEND_PAC", "origem_tabela": "ATENDIMENTO",
         "origem_colunas": ["CD_PACIENTE"], "destino_schema": "S",
         "destino_tabela": "PACIENTE", "destino_colunas": ["CD_PACIENTE"],
         "delete_rule": None},
    ]
    saida = mo.gerar_mermaid(arestas)
    assert saida.startswith("erDiagram")
    assert 'PACIENTE ||--o{ ATENDIMENTO : "CD_PACIENTE"' in saida


# ---------------------------------------------------------------------------
# Filtro de nomes e .env
# ---------------------------------------------------------------------------


def test_filtro_aceita_curinga_do_sql():
    nomes = ["PACIENTE", "PAC_HISTORICO", "ATENDIMENTO", "CONVENIO"]
    assert mo.filtrar_nomes(nomes, "PAC%,ATEND%") == ["PACIENTE", "PAC_HISTORICO", "ATENDIMENTO"]
    assert mo.filtrar_nomes(nomes, None) == nomes


def test_carregar_env_nao_sobrescreve_o_ambiente(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text('ORACLE_USER="do_arquivo"\n# comentario\nORACLE_PORT=1522\n')
    monkeypatch.setenv("ORACLE_USER", "do_shell")
    monkeypatch.delenv("ORACLE_PORT", raising=False)

    mo.carregar_env(arquivo)

    assert mo.os.environ["ORACLE_USER"] == "do_shell"
    assert mo.os.environ["ORACLE_PORT"] == "1522"


def test_restricao_gravavel_puxa_o_destino_da_aresta():
    restricao = {"owner": "S", "nome": "FK_ATEND_PAC", "tipo": "R", "tabela": "ATENDIMENTO",
                 "delete_rule": "CASCADE", "status": "ENABLED"}
    colunas = {("S", "FK_ATEND_PAC"): ["CD_PACIENTE"]}
    arestas = {"FK_ATEND_PAC": {"destino_schema": "S", "destino_tabela": "PACIENTE",
                                "destino_colunas": ["CD_PACIENTE"]}}

    saida = mo.restricao_gravavel(restricao, colunas, arestas)

    assert saida["colunas"] == ["CD_PACIENTE"]
    assert saida["ref_tabela"] == "PACIENTE"
    assert saida["delete_rule"] == "CASCADE"


def test_restricao_gravavel_de_pk_nao_tem_destino():
    restricao = {"owner": "S", "nome": "PK_PACIENTE", "tipo": "P", "tabela": "PACIENTE",
                 "delete_rule": None, "status": "ENABLED"}
    saida = mo.restricao_gravavel(restricao, {("S", "PK_PACIENTE"): ["CD_PACIENTE"]}, {})
    assert saida["ref_tabela"] is None and saida["ref_colunas"] is None


# ---------------------------------------------------------------------------
# Aspas no .env: senha com caractere especial e usuario case-sensitive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ('"p@ss#w0rd"', "p@ss#w0rd"),      # aspas duplas protegem o especial
        ("'p@ss#w0rd'", "p@ss#w0rd"),      # aspas simples idem
        ('p@ss#w0rd', "p@ss#w0rd"),        # sem aspas passa igual
        ('\'"meuUser"\'', '"meuUser"'),    # par interno sobrevive: identificador Oracle
        ('""', ""),                        # valor vazio entre aspas
        ('senha"', 'senha"'),              # aspas so no fim nao e delimitador
        ('"senha', '"senha'),              # nem so no inicio
        ("'", "'"),                        # uma aspa solta nao vira par
        ('"a"b"', 'a"b'),                  # so o par externo sai
    ],
)
def test_tirar_aspas_remove_um_par_so(bruto, esperado):
    assert mo.tirar_aspas(bruto) == esperado


def test_env_preserva_senha_com_caractere_especial(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text('ORACLE_PASSWORD="p@ss#w0rd=x"\n')
    monkeypatch.delenv("ORACLE_PASSWORD", raising=False)

    mo.carregar_env(arquivo)

    # O '=' depois do primeiro nao pode partir o valor, nem o '#' virar comentario
    assert mo.os.environ["ORACLE_PASSWORD"] == "p@ss#w0rd=x"


def test_env_entrega_usuario_como_identificador_citado(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text("""ORACLE_USER='"meuUser"'\n""")
    monkeypatch.delenv("ORACLE_USER", raising=False)

    mo.carregar_env(arquivo)

    # As duplas tem de chegar ao Oracle: sem elas o nome viraria MEUUSER
    assert mo.os.environ["ORACLE_USER"] == '"meuUser"'


def test_env_preserva_espaco_significativo_entre_aspas(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text('ORACLE_PASSWORD="  com espaco  "\n')
    monkeypatch.delenv("ORACLE_PASSWORD", raising=False)

    mo.carregar_env(arquivo)

    assert mo.os.environ["ORACLE_PASSWORD"] == "  com espaco  "
