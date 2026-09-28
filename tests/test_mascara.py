"""Testes da classificacao de sensibilidade que rodam sem banco e sem API.

O que da para fixar aqui e o contrato: como o pacote e cortado e como a resposta
do modelo e casada de volta com as colunas que a pediram. A chamada em si fica de
fora -- ela e a parte que so um provedor de verdade valida.
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import ia  # noqa: E402


def coluna(id_, nome="CAMPO", objeto="TAB", descricao="uma descrição qualquer"):
    return {
        "id": id_, "objeto": objeto, "nome": nome,
        "tipo_completo": "VARCHAR2(60)", "descricao_ia": descricao,
    }


def classificacao(*ids, categoria="nenhuma"):
    return ia.Classificacao(
        colunas=[
            ia.VereditoColuna(id=i, sensivel=False, categoria=categoria, motivo="m")
            for i in ids
        ]
    )


# ---------------------------------------------------------------------------
# Empacotamento
# ---------------------------------------------------------------------------


def test_pacote_corta_na_contagem():
    """Amarrado a COLUNAS_POR_PACOTE, nao ao numero de hoje: o tamanho e uma
    decisao de custo medida, e mudar de 50 nao pode quebrar o teste."""
    n = ia.COLUNAS_POR_PACOTE
    pacotes = ia.empacotar_colunas([coluna(i) for i in range(1, 2 * n + 6)])
    assert [len(p) for p in pacotes] == [n, n, 5]


def test_pacote_corta_nos_bytes_antes_da_contagem():
    """Descricao longa estoura o teto de bytes muito antes das 100 colunas.

    Cortar so pela contagem seria confiar que 100 descricoes cabem sempre. Prompt
    grande demais neste modelo nao devolve resposta pior: nao devolve resposta.
    """
    gordas = [coluna(i, descricao="x" * 5_000) for i in range(1, 21)]
    pacotes = ia.empacotar_colunas(gordas)
    assert all(len(p) < ia.COLUNAS_POR_PACOTE for p in pacotes)
    assert sum(len(p) for p in pacotes) == 20


def test_coluna_maior_que_o_teto_vai_sozinha():
    """Nao pode virar pacote vazio: o lote travaria num laço sem progresso."""
    enorme = [coluna(1, descricao="x" * (ia.COLUNAS_TETO_BYTES + 1))]
    assert [len(p) for p in ia.empacotar_colunas(enorme)] == [1]


def test_pacote_vazio_nao_gera_pacote():
    assert ia.empacotar_colunas([]) == []


def test_payload_leva_id_tabela_e_tipo():
    """Sem a tabela o modelo nao separa NAME de pessoa de NAME de procedimento."""
    payload = ia.montar_payload_mascara([coluna(7, "NAME", "GLBPERSON", "nome do paciente")])
    assert "7 | GLBPERSON.NAME (VARCHAR2(60)) | nome do paciente" in payload


# ---------------------------------------------------------------------------
# Reconciliacao da resposta -- onde um erro passaria despercebido
# ---------------------------------------------------------------------------


def test_resposta_completa_passa():
    pacote = [coluna(1), coluna(2), coluna(3)]
    vereditos = ia.conferir_vereditos(pacote, classificacao(1, 2, 3))
    assert [v.id for v in vereditos] == [1, 2, 3]


def test_resposta_fora_de_ordem_passa():
    """A ordem nao importa porque o casamento e por id, nao por posicao."""
    pacote = [coluna(1), coluna(2), coluna(3)]
    vereditos = ia.conferir_vereditos(pacote, classificacao(3, 1, 2))
    assert {v.id for v in vereditos} == {1, 2, 3}


def test_id_faltando_derruba_o_pacote():
    """O caso que, casado por posicao, gravaria o veredito da vizinha em cada coluna."""
    pacote = [coluna(1), coluna(2), coluna(3)]
    with pytest.raises(ia.GeracaoFalhou) as erro:
        ia.conferir_vereditos(pacote, classificacao(1, 2))
    assert "2" in erro.value.detalhe


def test_id_desconhecido_derruba_o_pacote():
    pacote = [coluna(1), coluna(2)]
    with pytest.raises(ia.GeracaoFalhou):
        ia.conferir_vereditos(pacote, classificacao(1, 2, 99))


def test_id_repetido_derruba_o_pacote():
    pacote = [coluna(1), coluna(2)]
    with pytest.raises(ia.GeracaoFalhou) as erro:
        ia.conferir_vereditos(pacote, classificacao(1, 1))
    assert "repetiu" in erro.value.motivo


def test_categoria_fora_da_lista_derruba_o_pacote():
    pacote = [coluna(1)]
    with pytest.raises(ia.GeracaoFalhou) as erro:
        ia.conferir_vereditos(pacote, classificacao(1, categoria="biometrico"))
    assert "biometrico" in erro.value.detalhe


@pytest.mark.parametrize("categoria", ia.CATEGORIAS)
def test_toda_categoria_da_lista_e_aceita(categoria):
    assert ia.conferir_vereditos([coluna(1)], classificacao(1, categoria=categoria))
