"""Testes da barra de filtros das listagens de /oracle.

Esta maquina monta SQL a partir de valor que vem do usuario, e ate agora nao
tinha teste nenhum. O que se fixa aqui e o contrato: que estado vira que
predicado, e que valor de escolha sai como PARAMETRO e nunca dentro do texto.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import ia, oracle  # noqa: E402

# O que a secao do dicionario declara: expressao para estado/escolha, predicado
# pronto para flag.
DISPONIVEIS = {
    "sensivel": "sensivel",
    "categoria": "sensivel_categoria",
    "sempre_nulo": "sempre_nulo",
    "registros": "objeto IN (SELECT nome FROM x)",
}


# ---------------------------------------------------------------------------
# Estado: sim / nao / nao avaliada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valor,esperado",
    [
        ("sim", "sempre_nulo"),
        ("nao", "sempre_nulo IS FALSE"),
        ("nao_avaliada", "sempre_nulo IS NULL"),
    ],
)
def test_estado_vira_predicado(valor, esperado):
    sql, params = oracle.montar_recorte(DISPONIVEIS, {"sempre_nulo": valor})
    assert sql == esperado
    assert params == ()


def test_estado_nao_usa_NOT():
    """`NOT <expr>` seria errado, nao so feio.

    Em SQL `NOT NULL` e NULL, entao a coluna nao avaliada ficaria de fora dos
    dois lados sem ninguem perceber -- e separar "tem valor" de "nao sei" e
    justamente para o que esta barra existe.
    """
    sql, _ = oracle.montar_recorte(DISPONIVEIS, {"sempre_nulo": "nao"})
    assert "NOT" not in sql
    assert "IS FALSE" in sql


def test_estado_desconhecido_e_ignorado():
    assert oracle.montar_recorte(DISPONIVEIS, {"sensivel": "talvez"}) == (None, ())


# ---------------------------------------------------------------------------
# Escolha: o valor tem de sair como parametro
# ---------------------------------------------------------------------------


def test_escolha_vira_parametro():
    sql, params = oracle.montar_recorte(DISPONIVEIS, {"categoria": "nome"})
    assert sql == "sensivel_categoria = %s"
    assert params == ("nome",)
    # O ponto do teste: o valor NAO aparece no texto do SQL
    assert "nome" not in sql


@pytest.mark.parametrize("categoria", ia.CATEGORIAS)
def test_toda_categoria_valida_e_aceita(categoria):
    """As opcoes saem de ia.CATEGORIAS, que e quem valida a resposta do modelo."""
    _, params = oracle.montar_recorte(DISPONIVEIS, {"categoria": categoria})
    assert params == (categoria,)


def test_escolha_fora_da_lista_e_ignorada():
    """A defesa contra injecao e a lista fechada, nao o escape."""
    veneno = "nome';DROP TABLE catalogo.coluna;--"
    sql, params = oracle.montar_recorte(DISPONIVEIS, {"categoria": veneno})
    assert sql is None and params == ()


# ---------------------------------------------------------------------------
# Flag e composicao
# ---------------------------------------------------------------------------


def test_flag_continua_gerando_o_predicado_da_secao():
    """A garantia de que as outras seis secoes nao mudaram."""
    sql, params = oracle.montar_recorte(DISPONIVEIS, {"registros": "1"})
    assert sql == DISPONIVEIS["registros"]
    assert params == ()


def test_filtros_compoem_em_and():
    sql, params = oracle.montar_recorte(
        DISPONIVEIS, {"categoria": "nome", "sempre_nulo": "nao", "registros": "1"}
    )
    assert sql.count(" AND ") == 2
    assert "sensivel_categoria = %s" in sql and "sempre_nulo IS FALSE" in sql
    assert params == ("nome",)


def test_filtro_que_a_secao_nao_declara_e_ignorado():
    """A barra so oferece o que vale, mas a URL pode vir digitada a mao."""
    assert oracle.montar_recorte({"registros": "x"}, {"categoria": "nome"}) == (None, ())


def test_sem_filtro_nenhum_nao_gera_recorte():
    assert oracle.montar_recorte(DISPONIVEIS, {}) == (None, ())


# ---------------------------------------------------------------------------
# A declaracao
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chave,param,rotulo,tipo", oracle.FILTROS)
def test_todo_filtro_tem_chave_param_e_tipo_conhecido(chave, param, rotulo, tipo):
    """A tela manda `param`; montar_recorte casa por `chave`. Um sem o outro
    perde o filtro em silencio."""
    assert chave and param and rotulo
    assert tipo in ("flag", "estado", "escolha")


@pytest.mark.parametrize(
    "chave", [c for c, _, _, t in oracle.FILTROS if t == "escolha"]
)
def test_todo_filtro_de_escolha_tem_opcoes(chave):
    """Escolha sem lista de opcoes aceitaria qualquer valor -- e a lista e a
    unica defesa contra o que vem na URL."""
    assert oracle.OPCOES.get(chave)
