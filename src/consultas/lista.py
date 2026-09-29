"""Motor das consultas: definição declarativa -> filtros, ordenação, página e CSV.

Uma consulta é um dict:
  slug, titulo, icone, descricao
  filtros:  [{nome, rotulo, tipo: 'mes'|'select'|'texto', opcoes: callable(ctx)|list, padrao}]
  colunas:  [{campo, rotulo, formato: 'texto'|'moeda'|'int'|'data'|'mono'|'pct'|'badge', num, sub, link}]
  carregar: callable(filtros: dict) -> list[dict]   (todas as linhas já filtradas)
  resumo:   callable(linhas) -> list[kpi]   (opcional)
A lista inteira vem de uma vez (as maiores têm poucos milhares de linhas) e a
página é recortada aqui; o CSV sai da mesma lista, então exporta exatamente o
filtro aplicado.
"""

import csv
import datetime
import decimal
import io

from .. import layout

POR_PAGINA = 50


def valores_filtros(definicao, params):
    saida = {}
    for f in definicao["filtros"]:
        valor = (params.get(f["nome"]) or "").strip()
        saida[f["nome"]] = valor if valor else f.get("padrao", "")
    return saida


def ordenar(linhas, definicao, ordem):
    campos = {c["campo"] for c in definicao["colunas"]}
    campo, _, sentido = (ordem or "").partition(":")
    if campo not in campos:
        return linhas, ""
    def chave(l):
        v = l.get(campo)
        return (v is None, v if not isinstance(v, str) else v.upper())
    return sorted(linhas, key=chave, reverse=sentido == "desc"), f"{campo}:{sentido or 'asc'}"


def paginar(linhas, pagina, por_pagina=POR_PAGINA):
    total = len(linhas)
    paginas = max(1, -(-total // por_pagina))
    pagina = min(max(1, pagina), paginas)
    inicio = (pagina - 1) * por_pagina
    recorte = linhas[inicio:inicio + por_pagina]
    info = {"pagina": pagina, "paginas": paginas, "total": total,
            "primeiro": inicio + 1 if recorte else 0, "ultimo": inicio + len(recorte)}
    info["numeros"] = layout.numeros_visiveis(pagina, paginas)
    return recorte, info


def _texto_csv(valor):
    if valor is None:
        return ""
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, (float, decimal.Decimal)):
        return f"{valor:.2f}".replace(".", ",")
    return str(valor)


def csv_de(linhas, definicao):
    """CSV pt-BR (separador ;, decimal com vírgula), com BOM para o Excel abrir acentuado."""
    buf = io.StringIO()
    escritor = csv.writer(buf, delimiter=";")
    colunas = [c for c in definicao["colunas"] if not c.get("so_tela")]
    escritor.writerow([c["rotulo"] for c in colunas])
    for l in linhas:
        escritor.writerow([_texto_csv(l.get(c["campo"])) for c in colunas])
    return "﻿" + buf.getvalue()


def gerar(definicao, usuario, params, formato=""):
    """(html | csv, status, tipo). params: dict do GET."""
    filtros = valores_filtros(definicao, params)
    erro = None
    try:
        linhas = definicao["carregar"](filtros)
    except Exception as falha:  # noqa: BLE001 -- fonte fora do ar vira aviso na página
        linhas, erro = [], {"motivo": getattr(falha, "motivo", str(falha)), "detalhe": getattr(falha, "dica", "")}
    linhas, ordem = ordenar(linhas, definicao, params.get("ordem"))
    if formato == "csv":
        return csv_de(linhas, definicao), 200, "text/csv"
    try:
        pagina = int(params.get("pagina") or 1)
    except ValueError:
        pagina = 1
    recorte, pag = paginar(linhas, pagina)
    opcoes = {f["nome"]: (f["opcoes"](filtros) if callable(f.get("opcoes")) else f.get("opcoes", []))
              for f in definicao["filtros"]}
    html = layout.render(
        "consultas/lista.html", definicao["titulo"], usuario, f"/consultas/{definicao['slug']}",
        consulta=definicao, filtros=filtros, opcoes=opcoes, linhas=recorte, pag=pag, ordem=ordem,
        resumo=definicao["resumo"](linhas) if definicao.get("resumo") else [], erro=erro,
        consultas=CONSULTAS_MENU)
    return html, 200, "text/html"


# preenchido por src/consultas/registro.py (abas da página)
CONSULTAS_MENU = []
