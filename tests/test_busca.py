"""Testes do ranking da busca semantica -- as partes que rodam sem banco e sem API.

O que se fixa aqui e a promessa que a tela faz ao usuario: que o numero exibido
seja monotono com a ordem das linhas, e que o zero da escala seja mesmo ruido.
A consulta SQL em si fica de fora; ela precisa de vetores no banco.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import busca  # noqa: E402

MODELO = "qwen/qwen3-embedding-8b"
BASE = busca.LINHA_DE_BASE[MODELO]


# ---------------------------------------------------------------------------
# Normalizacao do termo
# ---------------------------------------------------------------------------


def test_sem_acento_sobe_para_maiuscula_e_tira_acento():
    """Quem busca "internação" precisa casar com TDINTERNACAO: o Postgres daqui
    nao tem unaccent, entao a normalizacao acontece do lado do termo."""
    assert busca.sem_acento("internação") == "INTERNACAO"


def test_sem_acento_aguenta_none():
    assert busca.sem_acento(None) == ""


def test_tokens_descarta_palavra_curta():
    """"de"/"da"/"id" casariam com quase todo nome e so sujariam o lexical."""
    assert busca.tokens("cadastro de internação") == ["CADASTRO", "INTERNACAO"]


def test_tokens_de_termo_vazio():
    assert busca.tokens("   ") == []


# ---------------------------------------------------------------------------
# Prefixos excluidos da busca
# ---------------------------------------------------------------------------


def test_prefixos_separa_por_virgula_e_normaliza():
    assert busca.prefixos("bkp_, x") == ["BKP\\_%", "X%"]


def test_prefixos_ignora_vazio_e_espaco():
    assert busca.prefixos(" , ,  ") == []
    assert busca.prefixos("") == []
    assert busca.prefixos(None) == []


def test_prefixos_escapa_underline():
    """Em LIKE o _ e curinga: sem escape, "BKP_" excluiria BKPA e BKPX tambem."""
    assert busca.prefixos("bkp_") == ["BKP\\_%"]


def test_prefixos_escapa_porcento():
    assert busca.prefixos("a%b") == ["A\\%B%"]


def test_escapar_like_neutraliza_os_curingas():
    assert busca.escapar_like("BKP_") == "BKP\\_"
    assert busca.escapar_like("A%B") == "A\\%B"
    # A barra vai primeiro: escapada depois, ela escaparia o proprio escape
    assert busca.escapar_like("A\\_B") == "A\\\\\\_B"


def test_token_com_underline_nao_vira_curinga():
    """O token entra no SQL como padrao LIKE, mas lexical() compara substring
    literal. Sem escape "ADM_SSION" casaria ADMISSIONDATE so no SQL, e a
    relevancia exibida deixaria de bater com o ranking que os testes cobrem."""
    assert busca.lexical("ADMISSIONDATE", "ADM_SSION") == 0.0
    assert [busca.escapar_like(t) for t in busca.tokens("ADM_SSION")] == ["ADM\\_SSION"]


# ---------------------------------------------------------------------------
# Casamento lexical
# ---------------------------------------------------------------------------


def test_lexical_nome_exato_vale_tudo():
    assert busca.lexical("TDPACIENTE", "tdpaciente") == 1.0


def test_lexical_uma_palavra_contida():
    assert busca.lexical("TDINTERNACAO", "internação") == pytest.approx(0.6)


def test_lexical_metade_dos_tokens():
    """"cadastro" nao aparece, "internacao" sim -> metade de 0,6."""
    assert busca.lexical("TDINTERNACAO", "cadastro internação") == pytest.approx(0.3)


def test_lexical_nada_em_comum():
    assert busca.lexical("TDPACIENTE", "receita de bolo") == 0.0


def test_lexical_de_termo_so_com_palavra_curta():
    """Sem token util nao da para afirmar casamento nenhum -- e 0, nao erro."""
    assert busca.lexical("TDPACIENTE", "de da id") == 0.0


# ---------------------------------------------------------------------------
# Escala exibida
# ---------------------------------------------------------------------------


def test_relevancia_do_ruido_puro_e_zero():
    """O ponto de todo o desenho: cosseno na linha de base e ruido, nao acerto."""
    assert busca.relevancia(busca.score(BASE, "X", "y"), MODELO) == pytest.approx(0.0)


def test_relevancia_do_casamento_perfeito_e_cem():
    assert busca.relevancia(busca.score(1.0, "TDPAC", "tdpac"), MODELO) == pytest.approx(100.0)


def test_relevancia_nunca_fica_negativa():
    """Cosseno abaixo da linha de base existe; "-12 de relevancia" nao faz sentido."""
    assert busca.relevancia(busca.score(0.10, "X", "y"), MODELO) == 0.0


def test_relevancia_nunca_passa_de_cem():
    assert busca.relevancia(1.5, MODELO) == 100.0


def test_relevancia_de_modelo_nao_medido_usa_o_score_cru():
    """A linha de base e propria de cada modelo. Sem medida, mostrar o numero cru
    e mais honesto do que calibrar com a base emprestada de outro modelo."""
    assert busca.relevancia(0.5, "modelo-novo-qualquer") == pytest.approx(50.0)


def test_relevancia_e_monotona_no_score():
    """A tela ordena por score e exibe relevancia; se a relacao nao fosse
    monotona, apareceria 45 acima de 60 e a lista pareceria quebrada."""
    scores = [0.40, 0.55, 0.70, 0.85, 1.0]
    valores = [busca.relevancia(s, MODELO) for s in scores]
    assert valores == sorted(valores)


# ---------------------------------------------------------------------------
# Score: a nota que ordena
# ---------------------------------------------------------------------------


def test_score_soma_ponderada():
    esperado = busca.PESO_COS * 0.8 + busca.PESO_LEX * 1.0
    assert busca.score(0.8, "TDPAC", "tdpac") == pytest.approx(esperado)


def test_lexical_promove_com_cosseno_igual():
    """E para isto que o reforco existe: quem digita o nome da tabela quer ela."""
    com_nome = busca.score(0.70, "CAPADMREPORTITEM", "CAPADMREPORTITEM")
    sem_nome = busca.score(0.70, "CAPPAYMENTITEM", "CAPADMREPORTITEM")
    assert com_nome > sem_nome


def test_pesos_somam_um():
    """Se nao somassem, o score perfeito nao daria 1 e a escala nao fecharia em 100."""
    assert busca.PESO_COS + busca.PESO_LEX == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Consultas: o contrato que o banco cobra
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("escopo", busca.ESCOPOS)
def test_toda_consulta_filtra_por_modelo(escopo):
    """Sem embedding_modelo no WHERE o operador <=> nao devolve resultado ruim:
    levanta erro, porque a coluna guarda vetores de dimensoes diferentes."""
    assert "embedding_modelo = %(modelo)s" in busca.CONSULTA[escopo]


@pytest.mark.parametrize("escopo", busca.ESCOPOS)
def test_toda_consulta_ordena_e_limita(escopo):
    sql = busca.CONSULTA[escopo]
    assert "ORDER BY score DESC" in sql
    assert "LIMIT %(topk)s" in sql


@pytest.mark.parametrize("escopo", busca.ESCOPOS)
def test_toda_consulta_devolve_o_score_que_ordena(escopo):
    """A relevancia exibida sai do score, entao ele tem de vir na resposta."""
    assert "score" in busca.CONSULTA[escopo]


@pytest.mark.parametrize("escopo", busca.ESCOPOS)
def test_toda_consulta_respeita_os_prefixos_excluidos(escopo):
    """Inclusive a de campos, que filtra pelo nome da TABELA, nao do campo."""
    assert "LIKE ANY (%(excluir)s::text[])" in busca.CONSULTA[escopo]
    assert "upper(o.nome) LIKE ANY" in busca.CONSULTA[escopo]
