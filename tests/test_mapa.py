"""Testes do mapa semantico -- as partes que rodam sem banco.

O que se fixa aqui e o que a tela promete: que cada par de tabelas vire UMA
aresta (nao duas), que a classificacao separe FK de significado, e que a cor do
tema nao mude a cada F5. A consulta SQL fica de fora; ela precisa de vetores.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import mapa  # noqa: E402


def viz(origem, destino, cos):
    return {"origem": origem, "destino": destino, "cos": cos}


def fk(origem, destino):
    return {"origem": origem, "destino": destino}


# ---------------------------------------------------------------------------
# Normalizacao do par
# ---------------------------------------------------------------------------


def test_par_e_o_mesmo_nos_dois_sentidos():
    assert mapa.par("B", "A") == mapa.par("A", "B")


# ---------------------------------------------------------------------------
# Classificacao das arestas
# ---------------------------------------------------------------------------


def test_knn_dirigido_vira_uma_aresta_so():
    """A tem B entre os vizinhos e B tem A: e a mesma aresta. Duas linhas
    sobrepostas dobrariam o peso visual do par."""
    ligacoes = mapa.arestas([viz("A", "B", 0.80), viz("B", "A", 0.80)], [])
    assert len(ligacoes) == 1
    assert (ligacoes[0]["origem"], ligacoes[0]["destino"]) == ("A", "B")


def test_vizinhanca_sem_fk_e_sim():
    ligacoes = mapa.arestas([viz("A", "B", 0.80)], [])
    assert ligacoes[0]["tipo"] == "sim"


def test_fk_com_vizinhanca_e_ambos():
    """FK declarada que o significado confirma."""
    ligacoes = mapa.arestas([viz("A", "B", 0.80)], [fk("A", "B")])
    assert ligacoes[0]["tipo"] == "ambos"


def test_fk_sem_vizinhanca_e_fk():
    """O caso que a tela existe para mostrar: a ligacao esta no schema e nao no
    significado. CAPEQUIPMRENTALMAT -> CAPFINANCIALDOC da 0,514, que e ruido."""
    ligacoes = mapa.arestas([], [fk("A", "B")])
    assert ligacoes[0]["tipo"] == "fk"
    assert ligacoes[0]["cos"] is None


def test_fk_no_sentido_inverso_casa_com_a_vizinhanca():
    """A FK e dirigida e o kNN nao; sem normalizar as duas viravam arestas
    separadas e o par aparecia como 'sim' e 'fk' ao mesmo tempo."""
    ligacoes = mapa.arestas([viz("A", "B", 0.80)], [fk("B", "A")])
    assert len(ligacoes) == 1
    assert ligacoes[0]["tipo"] == "ambos"


def test_cosseno_altissimo_e_gemea_mesmo_com_fk():
    """Duplicata manda no tipo: e o achado mais acionavel da tela."""
    ligacoes = mapa.arestas([viz("A", "B", 0.99)], [fk("A", "B")])
    assert ligacoes[0]["tipo"] == "gemea"


def test_limiar_da_gemea_e_inclusivo():
    assert mapa.arestas([viz("A", "B", mapa.GEMEA)], [])[0]["tipo"] == "gemea"
    ligacoes = mapa.arestas([viz("A", "B", mapa.GEMEA - 0.01)], [])
    assert ligacoes[0]["tipo"] == "sim"


def test_arestas_saem_ordenadas():
    """O JSON tem de sair igual a cada request -- indice de aresta e posicional
    no cosmos."""
    ligacoes = mapa.arestas([viz("C", "D", 0.8), viz("A", "B", 0.8)], [])
    assert [(l["origem"], l["destino"]) for l in ligacoes] == [("A", "B"), ("C", "D")]


def test_piso_esta_acima_do_ruido_do_modelo():
    """O piso so faz sentido em relacao ao ruido medido: dois vetores sem relacao
    nenhuma ja pontuam 0,456 neste modelo."""
    from src import busca
    assert mapa.PISO > max(busca.LINHA_DE_BASE.values())


# ---------------------------------------------------------------------------
# Comunidades (os temas do schema)
# ---------------------------------------------------------------------------


def test_ligados_caem_no_mesmo_tema():
    ligacoes = mapa.arestas([viz("A", "B", 0.8), viz("B", "C", 0.8)], [])
    tema = mapa.comunidades(["A", "B", "C"], ligacoes)
    assert tema["A"] == tema["B"] == tema["C"]


def test_desligados_caem_em_temas_diferentes():
    ligacoes = mapa.arestas([viz("A", "B", 0.8), viz("C", "D", 0.8)], [])
    tema = mapa.comunidades(["A", "B", "C", "D"], ligacoes)
    assert tema["A"] == tema["B"]
    assert tema["C"] == tema["D"]
    assert tema["A"] != tema["C"]


def test_no_isolado_tem_tema_proprio():
    tema = mapa.comunidades(["A", "B", "SOZINHA"],
                            mapa.arestas([viz("A", "B", 0.8)], []))
    assert tema["SOZINHA"] not in (tema["A"],)


def test_aresta_so_de_fk_nao_agrupa():
    """Misturar o par 'fk' no tema juntaria justamente o que a tela quer mostrar
    separado: ligados no schema, distantes no significado."""
    tema = mapa.comunidades(["A", "B"], mapa.arestas([], [fk("A", "B")]))
    assert tema["A"] != tema["B"]


def test_temas_sao_reindexados_de_zero():
    """O JS usa o id direto como posicao na paleta -- id esparso estouraria."""
    nomes = ["A", "B", "C", "D"]
    tema = mapa.comunidades(nomes, mapa.arestas([viz("A", "B", 0.8)], []))
    assert sorted(set(tema.values())) == list(range(len(set(tema.values()))))


def test_comunidades_e_deterministico():
    """A cor do tema nao pode trocar a cada F5."""
    ligacoes = mapa.arestas(
        [viz("A", "B", 0.8), viz("B", "C", 0.8), viz("D", "E", 0.8)], []
    )
    nomes = ["E", "A", "C", "B", "D"]
    primeiro = mapa.comunidades(nomes, ligacoes)
    for _ in range(5):
        assert mapa.comunidades(list(reversed(nomes)), ligacoes) == primeiro


def test_comunidades_termina_em_grafo_ciclico():
    """Ciclo par e o caso classico de oscilacao do label propagation; PASSOS e o
    teto que garante o retorno."""
    ligacoes = mapa.arestas(
        [viz("A", "B", 0.8), viz("B", "C", 0.8), viz("C", "D", 0.8), viz("D", "A", 0.8)],
        [],
    )
    tema = mapa.comunidades(["A", "B", "C", "D"], ligacoes)
    assert len(tema) == 4


# ---------------------------------------------------------------------------
# Contrato das consultas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sql", [mapa.SQL_NOS, mapa.SQL_VIZINHOS, mapa.SQL_FKS])
def test_toda_consulta_filtra_por_modelo(sql):
    """<=> levanta erro entre dimensoes diferentes, e a coluna guarda vetores de
    modelos diferentes."""
    assert "embedding_modelo = %(modelo)s" in sql


@pytest.mark.parametrize("sql", [mapa.SQL_NOS, mapa.SQL_VIZINHOS, mapa.SQL_FKS])
def test_toda_consulta_respeita_os_prefixos_excluidos(sql):
    assert "%(excluir)s" in sql


def test_nos_saem_ordenados_por_nome():
    """A posicao na lista vira o indice do ponto no cosmos, e a aresta referencia
    indice. Ordem instavel trocaria as arestas de lugar."""
    assert "ORDER BY o.nome" in mapa.SQL_NOS


def test_fk_nao_traz_laco():
    """O cosmos nao desenha aresta de um no para ele mesmo."""
    assert "r.origem_tabela <> r.destino_tabela" in mapa.SQL_FKS
