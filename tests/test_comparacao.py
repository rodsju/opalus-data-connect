"""Partes puras de Oracle > Comparar: selecao, diferenca, prompt, aterramento e templates."""

import datetime
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import comparacao, ia, layout  # noqa: E402


def _col(nome, tipo="NUMBER(10)", nulo=True, pk=False):
    return {"nome": nome, "tipo_completo": tipo, "aceita_nulo": nulo, "eh_pk": pk,
            "comentario": None, "descricao_ia": None, "sempre_nulo": None}


def _obj(i, esquema, colunas, fks=(), indices=(), amostra=(), nome="CAPPAYMENT"):
    return {"id": i, "nome": nome, "tipo": "TABLE", "esquema": esquema, "esquema_id": i,
            "servidor": "IW", "num_registros": 10, "colunas": list(colunas),
            "fks": list(fks), "indices": list(indices), "descricao": None,
            "amostra": [{"dados": d} for d in amostra],
            "atualizado_em": datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc)}


def _par():
    a = _obj(1, "HML", [_col("ID", pk=True, nulo=False), _col("VALOR", "NUMBER(12,2)"),
                        _col("STATUS", "VARCHAR2(1)"), _col("SO_HML")],
             fks=[{"colunas": "IDBUDGET", "destino_tabela": "CAPBUDGET", "destino_colunas": "ID"}],
             indices=[{"nome": "IX1", "unico": True, "colunas": ["ID"]}])
    b = _obj(2, "PRD", [_col("ID", pk=True, nulo=False), _col("VALOR", "NUMBER(14,2)"),
                        _col("STATUS", "VARCHAR2(1)", nulo=False), _col("SO_PRD")],
             indices=[{"nome": "IX9", "unico": True, "colunas": ["ID"]},
                      {"nome": "IX2", "unico": False, "colunas": ["STATUS"]}])
    return comparacao.rotular([a, b])


# --------------------------------------------------------------------------
# Selecao
# --------------------------------------------------------------------------


def test_ids_validos_aceita_lista_e_virgula_sem_repetir():
    assert comparacao.ids_validos(["3,1", "2", "3"]) == [3, 1, 2]


@pytest.mark.parametrize("valores", [["1"], [], ["1,2,3,4,5,6,7"], ["1", "x"], ["1,1"]])
def test_ids_invalidos(valores):
    with pytest.raises(comparacao.ComparacaoInvalida):
        comparacao.ids_validos(valores)


def test_assinatura_ignora_a_ordem():
    assert comparacao.assinatura([90, 12, 57]) == comparacao.assinatura([12, 57, 90]) == "12,57,90"


def test_rotulo_leva_o_servidor_so_quando_o_schema_se_repete():
    a, b = _obj(1, "DBIW", []), _obj(2, "DBIW", [])
    b["servidor"] = "Outro"
    c = _obj(3, "PRD", [])
    comparacao.rotular([a, b, c])
    assert (a["rotulo"], b["rotulo"], c["rotulo"]) == (
        "IW/DBIW.CAPPAYMENT", "Outro/DBIW.CAPPAYMENT", "PRD.CAPPAYMENT")


# --------------------------------------------------------------------------
# Diferenca
# --------------------------------------------------------------------------


def test_diferenca_classifica_cada_coluna():
    dif = comparacao.diferenca(_par())
    classes = {linha["coluna"]: linha["classe"] for linha in dif["colunas"]}
    assert classes == {"ID": "igual", "VALOR": "tipo", "STATUS": "nulo",
                       "SO_HML": "ausente", "SO_PRD": "ausente"}
    # Ordem: as da primeira tabela, depois as novas da segunda
    assert [linha["coluna"] for linha in dif["colunas"]] == [
        "ID", "VALOR", "STATUS", "SO_HML", "SO_PRD"]
    assert dif["totais"] == {"colunas": 5, "iguais": 1, "divergentes": 2, "ausentes": 2,
                             "exclusivas": [1, 1]}


def test_pk_divergente():
    a = _obj(1, "A", [_col("ID", pk=True)])
    b = _obj(2, "B", [_col("ID", pk=False)])
    assert comparacao.diferenca([a, b])["colunas"][0]["classe"] == "pk"


def test_tres_tabelas_e_exclusiva_so_quando_esta_em_uma():
    objs = [_obj(1, "A", [_col("X"), _col("Y")]), _obj(2, "B", [_col("X"), _col("Y")]),
            _obj(3, "C", [_col("X")])]
    dif = comparacao.diferenca(objs)
    assert {linha["coluna"]: linha["classe"] for linha in dif["colunas"]} == {
        "X": "igual", "Y": "ausente"}
    # Y falta em C, mas existe em duas: nao e exclusiva de ninguem
    assert dif["totais"]["exclusivas"] == [0, 0, 0]


def test_fks_e_indices_presentes_so_de_um_lado():
    dif = comparacao.diferenca(_par())
    assert dif["fks"] == [{"chave": "IDBUDGET -> CAPBUDGET.ID", "presente": [True, False],
                           "classe": "ausente"}]
    # Indice compara pelas colunas, nao pelo nome (IX1 x IX9 e o mesmo indice)
    assert {x["chave"]: x["classe"] for x in dif["indices"]} == {
        "único (ID)": "igual", "(STATUS)": "ausente"}


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------


def test_payload_compacta_iguais_e_detalha_divergentes():
    objs = _par()
    texto, _ = comparacao.montar_payload(objs, comparacao.diferenca(objs))
    assert "Colunas idênticas em todas (1): ID" in texto
    assert "VALOR (tipo): [1] NUMBER(12,2) | [2] NUMBER(14,2)" in texto
    assert "SO_PRD (ausente): [1] ausente | [2] NUMBER(10)" in texto
    assert "IDBUDGET -> CAPBUDGET.ID -- só em [1]" in texto


def test_payload_divide_a_amostra_e_respeita_o_teto():
    linha = {"ID": 1, "TEXTO": "x" * 200}
    objs = _par()
    for o in objs:
        o["amostra"] = [{"dados": linha} for _ in range(50)]
    dif = comparacao.diferenca(objs)
    teto = 6_000
    texto, linhas = comparacao.montar_payload(objs, dif, teto=teto)
    assert len(texto) <= teto + 200  # folga das quebras de linha e cabecalhos da amostra
    por_tabela = [texto.count(f"[{i}] {o['rotulo']} ({linhas // 2} de 50 linhas)")
                  for i, o in enumerate(objs, 1)]
    assert por_tabela == [1, 1] and linhas > 0
    # Partes iguais: as duas tabelas levam o mesmo numero de linhas
    assert f"({linhas // 2} de 50 linhas)" in texto


def test_esquema_estrito_fecha_todos_os_objetos():
    esquema = ia._esquema_estrito(comparacao.Comparacao)

    def objetos(no):
        if isinstance(no, dict):
            if no.get("type") == "object":
                yield no
            for valor in no.values():
                yield from objetos(valor)
        elif isinstance(no, list):
            for item in no:
                yield from objetos(item)

    achados = list(objetos(esquema))
    assert achados and all(o["additionalProperties"] is False for o in achados)


# --------------------------------------------------------------------------
# Aterramento
# --------------------------------------------------------------------------


def test_aterrar_descarta_tabela_e_coluna_inventadas():
    objs = _par()
    analise = comparacao.Comparacao(
        resumo="r", semelhancas=[], recomendacoes=[],
        diferencas=[comparacao.Diferenca(aspecto="a", tabelas=["HML.CAPPAYMENT", "XPTO"],
                                         detalhe="d", impacto="i")],
        equivalencias=[
            comparacao.Equivalencia(conceito="so", colunas=[
                comparacao.ColunaRef(tabela="HML.CAPPAYMENT", coluna="SO_HML"),
                comparacao.ColunaRef(tabela="PRD.CAPPAYMENT", coluna="SO_PRD")]),
            # Coluna inventada: sobra uma referencia so, e a equivalencia cai
            comparacao.Equivalencia(conceito="falsa", colunas=[
                comparacao.ColunaRef(tabela="HML.CAPPAYMENT", coluna="VALOR"),
                comparacao.ColunaRef(tabela="PRD.CAPPAYMENT", coluna="NAO_EXISTE")]),
        ],
    )
    comparacao.aterrar(analise, objs)
    assert analise.diferencas[0].tabelas == ["HML.CAPPAYMENT"]
    assert [e.conceito for e in analise.equivalencias] == ["so"]


def test_vencida_quando_objeto_reimportado_depois():
    objs = _par()
    gravada = {"gerado_em": datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)}
    assert comparacao.vencida(gravada, objs)
    gravada["gerado_em"] = datetime.datetime(2026, 12, 1, tzinfo=datetime.timezone.utc)
    assert not comparacao.vencida(gravada, objs)
    assert not comparacao.vencida(None, objs)


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


def test_menu_tem_o_item():
    assert any(item["href"] == "/oracle/comparar"
               for grupo in layout.MENU for item in grupo["itens"])


def test_selecao_renderiza_opcoes_marcadas():
    html = layout.render(
        "oracle_comparar.html", "Comparar tabelas", None, "/oracle/comparar",
        nome="CAPPAYMENT", termo="", nome_sem_resultado=False, historico=[],
        minimo=2, maximo=6, aviso=None,
        opcoes=[{**_obj(1, "HML", []), "marcado": True},
                {**_obj(2, "PRD", []), "marcado": False}],
    )
    assert 'name="sel" value="1" checked' in html
    assert 'name="sel" value="2">' in html
    assert 'formaction="/oracle/comparar/ver"' in html


def test_resultado_renderiza_matriz_e_analise():
    objs = _par()
    dif = comparacao.diferenca(objs)
    ia_gravada = {
        "provedor": "anthropic", "modelo": "m", "resumo": "Mesma entidade.",
        "diferencas": [{"aspecto": "Valor", "tabelas": ["PRD.CAPPAYMENT"], "detalhe": "d",
                        "impacto": "i"}],
        "semelhancas": [], "recomendacoes": ["unificar"],
        "equivalencias": [{"conceito": "c", "colunas": [
            {"tabela": "HML.CAPPAYMENT", "coluna": "SO_HML"},
            {"tabela": "PRD.CAPPAYMENT", "coluna": "SO_PRD"}]}],
        "linhas_no_prompt": 4, "tokens_entrada": 1, "tokens_saida": 2,
        "gerado_em": datetime.datetime(2026, 12, 1), "gerado_por": None,
    }
    html = layout.render(
        "oracle_comparacao.html", "Comparação", None, "/oracle/comparar",
        objetos=objs, ids="1,2", dif=dif, texto_estado=comparacao.texto_estado, cards=[],
        ia=ia_gravada, ia_vencida=False, provedores=[], aviso=None,
    )
    assert "Mesma entidade." in html
    assert "HML.CAPPAYMENT.SO_HML ≈ PRD.CAPPAYMENT.SO_PRD" in html
    assert 'class="ds-cmp--tipo"' in html and "NUMBER(14,2)" in html
    assert "/esquema?id=1&amp;objeto=CAPPAYMENT" in html or "/esquema?id=1&objeto=CAPPAYMENT" in html
