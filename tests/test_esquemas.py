"""Pre-filtro de schema: escolha pelo cookie, retorno seguro e SQL das telas. Sem banco."""

import pytest

from src import api, esquemas, oracle

LISTA = [
    {"id": 3, "nome": "DBIWGERIATRICS", "servidor": "IW"},
    {"id": 8, "nome": "OUTRO", "servidor": "IW"},
]


def test_cookie_valido_escolhe_o_schema_dele():
    assert esquemas.escolher(LISTA, "8")["id"] == 8


@pytest.mark.parametrize("cookie", [None, "", "abc", "999"])
def test_cookie_invalido_ou_de_schema_apagado_cai_no_primeiro(cookie):
    assert esquemas.escolher(LISTA, cookie)["id"] == 3


def test_sem_schema_no_catalogo_nao_ha_escolha():
    assert esquemas.escolher([], "3") is None


@pytest.mark.parametrize("voltar,esperado", [
    ("/oracle/dicionario", "/oracle/dicionario"),
    ("/setup/lote?tarefa=embedding", "/setup/lote?tarefa=embedding"),
    # O objeto pode nao existir no schema novo
    ("/oracle/objetos/PACIENTE", "/oracle/objetos"),
    # Fora do app: redirect aberto
    ("//evil.example", "/oracle"),
    ("https://evil.example", "/oracle"),
    ("/\\evil.example", "/oracle"),
    ("", "/oracle"),
])
def test_retorno_depois_da_troca_so_vai_para_caminho_local(voltar, esperado):
    assert esquemas.destino_seguro(voltar) == esperado


@pytest.mark.parametrize("secao", sorted(oracle.SECOES))
def test_toda_listagem_declara_a_coluna_de_schema(secao):
    assert oracle.SECOES[secao]["esquema"].endswith("esquema_id")


def test_lista_poe_o_schema_antes_do_recorte_e_do_parametro_dele():
    config = oracle.SECOES["dicionario"]
    condicao, params = oracle.condicao_da_lista(config, 7, "sensivel_categoria = %s", ("CPF",))
    assert condicao == "vw_dicionario.esquema_id = %s AND sensivel_categoria = %s"
    assert params == (7, "CPF")


@pytest.mark.parametrize("secao", sorted(oracle.SECOES))
def test_filtros_por_nome_ficam_presos_ao_schema_da_linha(secao):
    """Sem trocar o {esq}, o subselect compararia o esquema dele com ele mesmo."""
    config = oracle.SECOES[secao]
    for predicado in oracle.filtros_da_secao(config).values():
        assert "{esq}" not in predicado
        if "SELECT" in predicado:
            assert f"= {config['esquema']}" in predicado


def test_api_deduz_o_schema_quando_o_nome_e_unico():
    um = [{"esquema_id": 3, "esquema": "DBIWGERIATRICS"}]
    assert api.esquema_do_objeto("PACIENTE", candidatos=um) == 3


def test_api_recusa_nome_ambiguo_sem_schema_no_corpo():
    dois = [{"esquema_id": 3, "esquema": "A"}, {"esquema_id": 8, "esquema": "B"}]
    with pytest.raises(api.EntradaInvalida) as erro:
        api.esquema_do_objeto("PACIENTE", candidatos=dois)
    assert "ambíguo" in erro.value.motivo
    assert api.esquema_do_objeto("PACIENTE", "B", candidatos=dois) == 8
    with pytest.raises(api.EntradaInvalida):
        api.esquema_do_objeto("PACIENTE", "C", candidatos=dois)
