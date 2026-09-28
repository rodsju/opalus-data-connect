"""Testes das partes de embeddings que rodam sem banco e sem API.

O que da para fixar aqui e o contrato: o literal que o cast ::vector aceita, o
hash que decide se um texto precisa voltar para a API, e o texto que cada linha
vira. A chamada HTTP em si fica de fora -- ela e a parte que so um provedor de
verdade valida.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import embeddings  # noqa: E402
from src import lote as lote_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Literal do pgvector
# ---------------------------------------------------------------------------


def test_vetor_para_pg_monta_o_literal_sem_espaco():
    assert embeddings.vetor_para_pg([0.5, -1.0, 2.0]) == "[0.5,-1.0,2.0]"


def test_vetor_para_pg_aceita_inteiro():
    """O provedor pode devolver int; o literal tem de sair como float mesmo assim."""
    assert embeddings.vetor_para_pg([1, 0]) == "[1.0,0.0]"


def test_vetor_para_pg_de_vetor_vazio():
    assert embeddings.vetor_para_pg([]) == "[]"


# ---------------------------------------------------------------------------
# Hash: e ele que evita pagar de novo pelo mesmo texto
# ---------------------------------------------------------------------------


def test_hash_e_estavel_para_o_mesmo_texto():
    assert embeddings.hash_texto("uma tabela") == embeddings.hash_texto("uma tabela")


def test_hash_muda_quando_o_texto_muda():
    assert embeddings.hash_texto("uma tabela") != embeddings.hash_texto("outra tabela")


def test_hash_nao_quebra_com_acento():
    assert len(embeddings.hash_texto("internação domiciliar")) == 64


# ---------------------------------------------------------------------------
# Textos que viram vetor
# ---------------------------------------------------------------------------


def test_texto_do_objeto_junta_nome_rotulo_resumo_e_funcao():
    texto = embeddings.texto_do_objeto(
        "PACIENTE",
        {"rotulo": "Cadastro de pacientes", "resumo": "Guarda os pacientes.",
         "funcao": "Base do prontuário."},
    )
    assert texto == "PACIENTE\nCadastro de pacientes\nGuarda os pacientes.\nBase do prontuário."


def test_texto_do_objeto_pula_pedaco_vazio():
    """funcao e dominio sao opcionais; linha em branco no meio so suja o vetor."""
    texto = embeddings.texto_do_objeto(
        "PACIENTE", {"rotulo": "", "resumo": "Guarda os pacientes.", "funcao": None}
    )
    assert texto == "PACIENTE\nGuarda os pacientes."


def test_texto_da_coluna_leva_a_tabela_junto():
    """Campo isolado nao se distingue: "Data de inicio" existe em dezenas de tabelas."""
    texto = embeddings.texto_da_coluna("ATENDIMENTO", "DT_INI", "Data de início.")
    assert texto == "ATENDIMENTO.DT_INI: Data de início."


# ---------------------------------------------------------------------------
# Quem precisa ir para a API
# ---------------------------------------------------------------------------


def _linha(hash_gravado, modelo):
    return {"id": 1, "embedding_hash": hash_gravado, "embedding_modelo": modelo}


def test_pendente_quando_nunca_foi_vetorizado():
    linhas = [_linha(None, None)]
    assert embeddings._pendentes(linhas, {1: "texto"}, "m1") == linhas


def test_nao_pendente_quando_texto_e_modelo_batem():
    linhas = [_linha(embeddings.hash_texto("texto"), "m1")]
    assert embeddings._pendentes(linhas, {1: "texto"}, "m1") == []


def test_pendente_quando_o_texto_mudou():
    linhas = [_linha(embeddings.hash_texto("texto antigo"), "m1")]
    assert embeddings._pendentes(linhas, {1: "texto novo"}, "m1") == linhas


def test_pendente_quando_so_o_modelo_mudou():
    """Vetor de outro modelo nao se compara: o operador <=> recusa outra dimensao."""
    linhas = [_linha(embeddings.hash_texto("texto"), "m1")]
    assert embeddings._pendentes(linhas, {1: "texto"}, "m2") == linhas


# ---------------------------------------------------------------------------
# Recorte do lote -- o WHERE que o "aplicar as N do filtro" reaproveita
# ---------------------------------------------------------------------------


def test_onde_sem_filtro_nem_termo_nao_gera_where():
    assert lote_mod._onde((), "") == ("", ())


def test_onde_combina_filtro_e_termo():
    onde, params = lote_mod._onde({"registros"}, "PAC")
    assert onde == " WHERE o.tem_registros AND o.nome ILIKE %s"
    assert params == ("%PAC%",)


def test_onde_soma_os_filtros_com_and():
    onde, _ = lote_mod._onde({"registros", "sem_vetor"}, "")
    assert onde.startswith(" WHERE ")
    assert " AND " in onde


def test_filtro_de_vetor_exige_descricao():
    """Tabela sem descricao nao tem texto para vetorizar -- entraria so para falhar."""
    onde, _ = lote_mod._onde({"sem_vetor"}, "")
    assert "o.embedding IS NULL" in onde
    assert "descricao_ia" in onde


@pytest.mark.parametrize("chave,param", [(c, p) for c, p, _, _ in lote_mod.FILTROS])
def test_todo_filtro_tem_chave_e_param(chave, param):
    """A tela manda `param`; o _onde casa por `chave`. Um sem o outro perde o filtro."""
    assert chave and param
