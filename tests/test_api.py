"""Testes da API de descricoes que rodam sem banco e sem provedor.

O que da para fixar aqui e a semantica do merge -- a parte que decide o que
sobrevive a um corpo parcial. A gravacao e a vetorizacao ficam de fora: sao
integracao, e o que elas fazem ja esta coberto pelo proprio Postgres.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import api  # noqa: E402

NOMES = {"ID", "NOME", "DATA"}


def campo(coluna, descricao):
    return api.CampoEntrada(coluna=coluna, descricao=descricao)


def por_nome(campos):
    return {c["coluna"]: c["descricao"] for c in campos}


# --------------------------------------------------------------------------
# mesclar_campos
# --------------------------------------------------------------------------


def test_campo_novo_nao_apaga_os_outros():
    """O caso que motiva o merge: corrigir um campo de uma tabela larga."""
    atuais = [{"coluna": "ID", "descricao": "chave"}, {"coluna": "NOME", "descricao": "velho"}]
    saida = por_nome(api.mesclar_campos(atuais, [campo("NOME", "novo")], NOMES))
    assert saida == {"ID": "chave", "NOME": "novo"}


def test_campo_inedito_entra():
    saida = por_nome(api.mesclar_campos([], [campo("DATA", "quando")], NOMES))
    assert saida == {"DATA": "quando"}


def test_descricao_vazia_remove_o_campo():
    atuais = [{"coluna": "ID", "descricao": "chave"}, {"coluna": "NOME", "descricao": "x"}]
    saida = por_nome(api.mesclar_campos(atuais, [campo("NOME", "   ")], NOMES))
    assert saida == {"ID": "chave"}


def test_remover_campo_que_nao_existe_nao_explode():
    saida = por_nome(api.mesclar_campos([], [campo("DATA", "")], NOMES))
    assert saida == {}


def test_coluna_fora_do_catalogo_e_recusada():
    """Sem isto o nome errado entraria no jsonb e nunca casaria com a coluna."""
    with pytest.raises(api.EntradaInvalida) as erro:
        api.mesclar_campos([], [campo("ID_INEXISTENTE", "x")], NOMES)
    assert "ID_INEXISTENTE" in erro.value.motivo


def test_caixa_errada_conta_como_coluna_inexistente():
    """Oracle grava em maiusculas; casar sem caixa esconderia o erro de quem chama."""
    with pytest.raises(api.EntradaInvalida):
        api.mesclar_campos([], [campo("nome", "x")], NOMES)


def test_descricao_e_aparada():
    saida = por_nome(api.mesclar_campos([], [campo("ID", "  chave  ")], NOMES))
    assert saida == {"ID": "chave"}


# --------------------------------------------------------------------------
# _escolher: ausente mantem, presente vence
# --------------------------------------------------------------------------


def test_ausente_mantem_o_gravado():
    assert api._escolher(None, "gravado") == "gravado"


def test_presente_vence():
    assert api._escolher("novo", "gravado") == "novo"


def test_string_vazia_apaga():
    """"" e valor, nao ausencia -- e a unica forma de limpar um campo."""
    assert api._escolher("", "gravado") == ""


def test_ausente_sem_gravado_cai_no_padrao():
    assert api._escolher(None, None) == ""
    assert api._escolher(None, None, padrao=None) is None


# --------------------------------------------------------------------------
# Validacao do corpo
# --------------------------------------------------------------------------


def test_campo_desconhecido_no_corpo_e_recusado():
    """extra=forbid: um 'rotuloo' aceito em silencio viraria dado perdido."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        api.ObjetoEntrada(nome="TAB", rotuloo="typo")


def test_so_o_nome_e_obrigatorio():
    entrada = api.ObjetoEntrada(nome="TAB")
    assert entrada.rotulo is None and entrada.campos is None


# --------------------------------------------------------------------------
# agrupar_por_objeto: a planilha vira uma escrita por tabela
# --------------------------------------------------------------------------


def linha(objeto, coluna, descricao="texto"):
    return api.LinhaDicionario(objeto=objeto, coluna=coluna, descricao=descricao)


def test_linhas_da_mesma_tabela_viram_um_grupo():
    """E o que faz a planilha ser barata: uma ida a API de embeddings por tabela."""
    grupos = api.agrupar_por_objeto(
        [linha("A", "X"), linha("B", "Y"), linha("A", "Z")]
    )
    assert list(grupos) == ["A", "B"]
    assert [c.coluna for c in grupos["A"]] == ["X", "Z"]
    assert [c.coluna for c in grupos["B"]] == ["Y"]


def test_ordem_de_chegada_e_preservada():
    grupos = api.agrupar_por_objeto([linha("Z", "1"), linha("A", "2")])
    assert list(grupos) == ["Z", "A"]


def test_linha_repetida_vale_a_ultima():
    """Planilha com a mesma coluna duas vezes: vence a de baixo, como se espera."""
    grupos = api.agrupar_por_objeto(
        [linha("A", "X", "primeira"), linha("A", "X", "segunda")]
    )
    saida = por_nome(api.mesclar_campos([], grupos["A"], {"X"}))
    assert saida == {"X": "segunda"}


def test_grupo_vira_campo_do_mesmo_tipo_do_outro_endpoint():
    """Os dois endpoints convergem em mesclar_campos; o tipo tem de ser o mesmo."""
    grupos = api.agrupar_por_objeto([linha("A", "X")])
    assert all(isinstance(c, api.CampoEntrada) for c in grupos["A"])


def test_descricao_e_obrigatoria_na_linha_do_dicionario():
    """A linha existe para trazer uma descrição; sem ela nao ha o que gravar."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        api.LinhaDicionario(objeto="A", coluna="X")
