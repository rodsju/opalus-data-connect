"""Assistente de consulta: checagem, teto de linhas, READ ONLY, mascara e tela."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import consulta, layout  # noqa: E402

# --------------------------------------------------------------------------
# Checagem: o que passa
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sql", [
    "SELECT * FROM CAPPAYMENT",
    "select id, valor from cappayment where status = 'A'",
    "WITH x AS (SELECT id FROM CAPPAYMENT) SELECT * FROM x",
    "SELECT a.id, b.id AS id_b FROM CAPPAYMENT a JOIN CAPBUDGET b ON b.id = a.idbudget",
    "SELECT * FROM (SELECT id FROM CAPPAYMENT) t",
    "SELECT * FROM CAPPAYMENT ORDER BY id FETCH FIRST 10 ROWS ONLY",
    "(SELECT id FROM A) UNION ALL (SELECT id FROM B)",
    # Palavra proibida DENTRO de texto nao e comando
    "SELECT * FROM CAPPAYMENT WHERE obs = 'DELETE FROM X; DROP TABLE Y'",
    "SELECT q'[it's; DROP]' AS t FROM dual",
    # Coluna que so CONTEM a palavra
    "SELECT deleted_at, updated_by, comments FROM CAPPAYMENT",
    "SELECT * FROM CAPPAYMENT -- comentario com DELETE\n WHERE id = 1",
])
def test_validar_aceita(sql):
    assert consulta.validar(sql)


def test_ponto_e_virgula_final_sai_e_literal_fica_intacto():
    assert consulta.validar("SELECT 'a;b' AS x FROM dual;  ") == "SELECT 'a;b' AS x FROM dual"


def test_comentario_sai_do_executavel():
    assert "segredo" not in consulta.validar("SELECT 1 /* segredo */ FROM dual")


# --------------------------------------------------------------------------
# Checagem: o que e recusado
# --------------------------------------------------------------------------


@pytest.mark.parametrize("sql", [
    "",
    "   ;  ",
    "SELECT 1 FROM dual; DROP TABLE CAPPAYMENT",
    "SELECT 1 FROM dual /*x*/; DELETE FROM CAPPAYMENT",
    "DELETE FROM CAPPAYMENT",
    "UPDATE CAPPAYMENT SET valor = 0",
    "INSERT INTO CAPPAYMENT VALUES (1)",
    "MERGE INTO CAPPAYMENT USING dual ON (1=1) WHEN MATCHED THEN UPDATE SET valor = 0",
    "TRUNCATE TABLE CAPPAYMENT",
    "CREATE TABLE x AS SELECT * FROM CAPPAYMENT",
    "BEGIN NULL; END;",
    "DECLARE x NUMBER; BEGIN NULL; END;",
    "SELECT * FROM CAPPAYMENT FOR UPDATE",
    "SELECT id INTO v FROM CAPPAYMENT",
    "SELECT * FROM CAPPAYMENT@OUTRO_BANCO",
    "SELECT DBMS_RANDOM.VALUE FROM dual",
    "SELECT UTL_HTTP.REQUEST('http://x') FROM dual",
    "SELECT * FROM SYS.USER$",
    'SELECT * FROM "SYS"."USER$"',
    "SELECT * FROM V$SESSION",
    "SELECT * FROM DBA_USERS",
    "SELECT HTTPURITYPE('http://x').getclob() FROM dual",
    "WITH FUNCTION f RETURN NUMBER IS BEGIN RETURN 1; END; SELECT f FROM dual",
    "EXPLAIN PLAN FOR SELECT 1 FROM dual",
    "SELECT 'sem fechar FROM dual",
    "SELECT 1 /* sem fechar FROM dual",
])
def test_validar_recusa(sql):
    with pytest.raises(consulta.ConsultaRecusada):
        consulta.validar(sql)


def test_recusa_texto_grande_demais():
    with pytest.raises(consulta.ConsultaRecusada):
        consulta.validar("SELECT 1 FROM dual WHERE 'x' = '" + "x" * consulta.TETO_SQL_BYTES + "'")


def test_recusa_diz_o_que_achou():
    with pytest.raises(consulta.ConsultaRecusada) as info:
        consulta.validar("WITH x AS (SELECT 1 a FROM dual) DELETE FROM x")
    assert "DELETE" in info.value.detalhe


def test_embrulho_aplica_o_teto_no_banco():
    assert consulta.embrulhar("SELECT 1 FROM dual").endswith(
        f"WHERE ROWNUM <= {consulta.LIMITE + 1}")


# --------------------------------------------------------------------------
# Execucao: cursor e conexao falsos
# --------------------------------------------------------------------------


class _Cursor:
    def __init__(self, linhas, colunas=("ID", "NOME"), erro_no_embrulho=None):
        self._linhas = linhas
        self.description = [(c,) for c in colunas]
        self.executados = []
        self.fetches = 0
        self.erro_no_embrulho = erro_no_embrulho
        self.fechado = False

    def execute(self, sql):
        self.executados.append(sql)
        if self.erro_no_embrulho and "ROWNUM" in sql:
            erro, self.erro_no_embrulho = self.erro_no_embrulho, None
            raise erro

    def fetchmany(self, n):
        self.fetches += 1
        return self._linhas[:n]

    def fetchall(self):  # pragma: no cover - se for chamado, o teste falha
        raise AssertionError("fetchall nunca pode ser usado")

    def close(self):
        self.fechado = True


class _Conexao:
    def __init__(self, cursor):
        self._cursor = cursor
        self.rollbacks = 0

    def cursor(self):
        return self._cursor

    def rollback(self):
        self.rollbacks += 1


def test_ordem_schema_readonly_query_e_rollback():
    cursor = _Cursor([(1, "a")])
    conexao = _Conexao(cursor)
    consulta.rodar(conexao, "DS_IW", "SELECT id, nome FROM X")
    assert cursor.executados[0] == "ALTER SESSION SET CURRENT_SCHEMA = DS_IW"
    assert cursor.executados[1] == "SET TRANSACTION READ ONLY"
    assert "ROWNUM <= 201" in cursor.executados[2]
    assert conexao.rollbacks == 1 and cursor.fechado
    assert conexao.call_timeout == consulta.TEMPO_MAXIMO_MS


def test_teto_de_200_com_um_fetch_so():
    cursor = _Cursor([(i, "x") for i in range(500)])
    colunas, linhas, truncada, _ = consulta.rodar(_Conexao(cursor), "DS_IW", "SELECT 1 FROM X")
    assert len(linhas) == consulta.LIMITE == 200
    assert truncada and cursor.fetches == 1


def test_exatamente_200_nao_e_truncada():
    cursor = _Cursor([(i, "x") for i in range(200)])
    _, linhas, truncada, _ = consulta.rodar(_Conexao(cursor), "DS_IW", "SELECT 1 FROM X")
    assert len(linhas) == 200 and not truncada


def test_rollback_mesmo_com_erro():
    cursor = _Cursor([], erro_no_embrulho=RuntimeError("ORA-00942"))
    conexao = _Conexao(cursor)
    with pytest.raises(RuntimeError):
        consulta.rodar(conexao, "DS_IW", "SELECT 1 FROM X")
    assert conexao.rollbacks == 1 and cursor.fechado


def test_coluna_repetida_roda_crua_mas_continua_com_teto():
    class _Ora:
        code = 918

    cursor = _Cursor([(i, i) for i in range(300)], colunas=("ID", "ID"),
                     erro_no_embrulho=RuntimeError(_Ora()))
    _, linhas, truncada, _ = consulta.rodar(
        _Conexao(cursor), "DS_IW", "SELECT a.id, b.id FROM A, B")
    assert cursor.executados[-1] == "SELECT a.id, b.id FROM A, B"
    assert len(linhas) == 200 and truncada and cursor.fetches == 1


def test_schema_com_nome_estranho_nao_vai_para_o_alter_session():
    with pytest.raises(consulta.ConsultaFalhou):
        consulta.rodar(_Conexao(_Cursor([])), "DS_IW; DROP", "SELECT 1 FROM X")


def test_mascara_sensivel_e_mantem_nulo():
    cursor = _Cursor([(1, "Maria da Silva"), (2, None)], colunas=("ID", "NM_PACIENTE"))
    colunas, linhas, _, mascaradas = consulta.rodar(
        _Conexao(cursor), "DS_IW", "SELECT 1 FROM X", frozenset({"NM_PACIENTE"}))
    assert linhas == [[1, consulta.MASCARA], [2, None]]
    assert mascaradas == ["NM_PACIENTE"]


def test_muitas_colunas_recusa():
    cursor = _Cursor([], colunas=[f"C{i}" for i in range(consulta.MAX_COLUNAS + 1)])
    with pytest.raises(consulta.ConsultaFalhou):
        consulta.rodar(_Conexao(cursor), "DS_IW", "SELECT * FROM X")


def test_celula_corta_texto_e_esconde_binario():
    assert consulta.celula("x" * 5000).endswith("…")
    assert len(consulta.celula("x" * 5000)) == consulta.MAX_TEXTO + 1
    assert consulta.celula(b"\x00\x01") == "‹binário 2 bytes›"

    class _Clob:
        type = "DB_TYPE_CLOB"

        def size(self):
            return 10_000

        def read(self, inicio, n):
            return "y" * n

    assert consulta.celula(_Clob()) == "y" * consulta.MAX_TEXTO + "…"


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------


def _tabela(nome, n_colunas=3):
    return {"nome": nome, "tipo": "TABLE", "num_registros": 10, "rotulo": "Pagamento",
            "resumo": "Pagamentos a fornecedor",
            "colunas": [{"nome": f"C{i}", "tipo_completo": "NUMBER", "eh_pk": i == 0,
                         "aceita_nulo": i != 0, "descricao_ia": "d"} for i in range(n_colunas)],
            "fks": [{"colunas": "C1", "destino_tabela": "CAPBUDGET", "destino_colunas": "ID"}]}


def test_contexto_tem_dicionario_e_respeita_o_teto():
    tabelas = [_tabela(f"T{i}", 40) for i in range(30)]
    texto, usados = consulta.montar_contexto("pagamentos por status", tabelas, teto=4_000)
    assert len(texto.encode()) <= 4_000
    assert usados and len(usados) < 30
    assert "## T0 (TABLE" in texto and "C0 NUMBER PK" in texto
    assert "FK (C1) -> CAPBUDGET(ID)" in texto


def test_nomes_digitados():
    assert consulta.nomes_digitados("cappayment, CAPBUDGET  cappayment;x") == [
        "CAPPAYMENT", "CAPBUDGET", "X"]


def test_esquema_estrito_da_sugestao():
    from src import ia
    esquema = ia._esquema_estrito(consulta.Sugestao)
    assert esquema["additionalProperties"] is False


# --------------------------------------------------------------------------
# Tela
# --------------------------------------------------------------------------


def test_menu_renomeado_e_com_o_assistente():
    titulos = [grupo["titulo"] for grupo in layout.MENU]
    assert "Fontes de dados" in titulos and "Oracle" not in titulos
    assert any(item["href"] == "/oracle/consulta"
               for grupo in layout.MENU for item in grupo["itens"])


def _render(**extra):
    base = dict(
        esquema={"id": 1, "nome": "DS_IW", "servidor": "IW"}, sql="", pedido="",
        tabelas="", aba="sql", modo="sql", provedor="", pares=[], sugestao=None,
        resultado=None, cards=[], historico=[], cobertura=None, limite=200,
        tempo_maximo=30, mascara="*****", aviso=None,
    )
    base.update(extra)
    return layout.render("oracle_consulta.html", "Assistente de consulta", None,
                         "/oracle/consulta", **base)


def test_resultado_renderiza_e_escapa():
    html = _render(resultado={
        "colunas": ["ID", "NM_PACIENTE", "OBS"], "linhas": [[1, "*****", "<script>x</script>"]],
        "truncada": True, "mascaradas": ["NM_PACIENTE"], "ms": 12, "sql": "SELECT 1"})
    assert "Resultado cortado em 200 linhas" in html
    assert "ds-consulta-mascarada" in html
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html


def test_sugestao_preenche_o_editor_sem_resultado():
    html = _render(aba="prompt", modo="prompt", sql="SELECT * FROM CAPPAYMENT",
                   sugestao={"explicacao": "Lista pagamentos.", "premissas": ["status A"],
                             "avisos": [], "tabelas": ["CAPPAYMENT"], "via": "lexical",
                             "provedor": "p", "modelo": "m", "tokens_entrada": 1,
                             "tokens_saida": 2})
    assert "Lista pagamentos." in html
    assert ">SELECT * FROM CAPPAYMENT</textarea>" in html
    assert "Resultado" not in html.split("Suas últimas consultas")[0].split("Sugestão da IA")[1]


def test_aviso_de_recusa():
    html = _render(aviso={"motivo": "Comando não permitido numa consulta",
                          "detalhe": "Encontrado: DELETE."})
    assert "Comando não permitido" in html
