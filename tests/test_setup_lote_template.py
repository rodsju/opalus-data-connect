"""Regressao do recorte perdido entre a tela e o disparo do lote.

O bug: a pagina tem dois <form> irmaos -- um GET com o filtro e um POST que
dispara. Form HTML nao aninha, entao os campos do filtro nunca entravam no POST,
e "aplicar as N do filtro" chegava ao servidor sem filtro nenhum: o lote pegava o
catalogo inteiro em vez das N tabelas que a tela mostrava.

O SQL sempre esteve certo (lote._onde e compartilhado pela listagem e pelo
disparo); o que faltava eram os argumentos. Por isso o teste e da template: e la
que o recorte tem de viajar junto.
"""

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import layout  # noqa: E402

CONTEXTO = {
    "linhas": [],
    "total": 87,
    "mostrando": 0,
    "filtros": [
        {"param": "com_registros", "rotulo": "Só com registros", "ativo": True},
        {"param": "sem_descricao", "rotulo": "Só sem descrição", "ativo": False},
        {"param": "sem_vetor", "rotulo": "Só sem vetor", "ativo": True},
    ],
    "termo": "PAC",
    "paralelismo": 4,
    "pares": [],
    "tarefa": "embedding",
    "tarefas": [{"valor": "embedding", "rotulo": "Lote de vetores", "ativa": True}],
    "coluna_feito": "Vetor",
    "campo_feito": "vetorizada",
    "rotulo_feito": "vetorizada",
    "confirmacao": "Isso vai vetorizar {n} tabelas. Confirma?",
    "rotulos": {"descricao": "descrições", "embedding": "vetores", "mascara": "sensibilidade"},
    "estimativa": {"tabelas": 87, "duracao": "4min", "tokens_entrada": 0, "tokens_saida": 0},
    "aberto": None,
    "recentes": [],
    "aviso": None,
}


def _form_de_disparo(html):
    """So o <form> do POST -- o do filtro tem os mesmos names e confundiria o teste."""
    inicio = html.index('id="form-lote"')
    return html[inicio:html.index("</form>", inicio)]


def _renderizar(**mudancas):
    return layout.render("setup_lote.html", "Lote", None, "/setup/lote", **{**CONTEXTO, **mudancas})


def test_form_de_disparo_leva_o_termo_da_busca():
    form = _form_de_disparo(_renderizar())
    assert '<input type="hidden" name="q" value="PAC">' in form


def test_form_de_disparo_leva_os_filtros_marcados():
    form = _form_de_disparo(_renderizar())
    assert '<input type="hidden" name="com_registros" value="1">' in form
    assert '<input type="hidden" name="sem_vetor" value="1">' in form


def test_form_de_disparo_nao_leva_filtro_desmarcado():
    """Mandar tudo faria o oposto do bug: um recorte mais estreito que o da tela."""
    form = _form_de_disparo(_renderizar())
    assert "sem_descricao" not in form


def test_form_de_disparo_leva_a_tarefa():
    form = _form_de_disparo(_renderizar())
    assert '<input type="hidden" name="tarefa" value="embedding">' in form


def test_sem_filtro_nenhum_o_form_nao_inventa_recorte():
    filtros = [dict(f, ativo=False) for f in CONTEXTO["filtros"]]
    form = _form_de_disparo(_renderizar(filtros=filtros, termo=""))
    assert '<input type="hidden" name="q" value="">' in form
    assert not re.search(r'name="(com_registros|sem_descricao|sem_vetor)"', form)


def test_form_de_filtro_continua_mandando_o_recorte_na_querystring():
    """A outra metade: o GET e quem monta a URL que a tela usa para se refazer."""
    html = _renderizar()
    filtro = html[html.index('class="ds-busca"'):html.index('id="form-lote"')]
    assert 'name="q"' in filtro
    assert 'name="com_registros"' in filtro
