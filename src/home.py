"""Conteudo da rota /: pagina HTML no layout padrao, com o miolo em branco."""

from . import layout

PAYLOAD = {"status": "all goods, have a nice day!"}


def gerar_pagina(usuario=None):
    return layout.render("home.html", "Início", usuario, "/"), 200
