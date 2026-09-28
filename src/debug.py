"""Conteudo da rota /debug: pagina HTML para humanos, JSON para ferramentas."""

from . import layout, usuario as usuario_mod


def montar_identificacao(usuario):
    if usuario:
        return [
            ("E-mail", usuario["email"]),
            ("Iniciais", usuario["iniciais"]),
            ("Origem", f"header {usuario_mod.HEADER_USUARIO} ou variável de ambiente"),
        ]
    return [
        ("E-mail", "—"),
        ("Origem", f"nenhum {usuario_mod.HEADER_USUARIO} recebido"),
    ]


def gerar_pagina(request, usuario=None):
    html = layout.render(
        "debug.html",
        "Debug",
        usuario,
        "/debug",
        identificacao=montar_identificacao(usuario),
        headers=sorted(request.headers.items()),
    )
    return html, 200
