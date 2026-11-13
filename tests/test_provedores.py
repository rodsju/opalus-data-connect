"""Validação do cadastro de provedores (Setup > AI Providers). Sem banco."""

import pytest

from src import provedores


def test_provedor_de_decisao_so_com_tipo_decisions():
    provedores.validar("Jev", "decisions", ["typesafe/jev-1.13"], "decisao", "k", criando=True)
    for tipo, capacidade in (("openai", "decisao"), ("decisions", "llm")):
        with pytest.raises(provedores.ConfiguracaoInvalida):
            provedores.validar("Jev", tipo, ["m"], capacidade, "k", criando=True)
