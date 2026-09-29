"""Galeria: todos os blocos com dados de amostra e a explicação de cada item.

Não toca no Oracle -- serve para ver o visual e ler "como é calculado" sem VPN.
"""

from .. import layout
from . import relatorios


def gerar_pagina(usuario):
    blocos = [relatorios.descrever(b, b.montar_amostra()) for b in relatorios.BLOCOS]
    onde = {
        relatorios.slug_do_bloco(b): r["titulo"]
        for r in relatorios.RELATORIOS.values()
        for b in r["blocos"]
    }
    for bloco in blocos:
        bloco["relatorio"] = onde.get(bloco["slug"])
    html = layout.render(
        "reports/galeria.html",
        "Blocos de relatório",
        usuario,
        "/reports/blocos",
        blocos=blocos,
        abas=relatorios.menu_relatorios(),
    )
    return html, 200
