"""Camada de apresentacao compartilhada pelas paginas.

Todo o HTML vive em src/templates, renderizado com Jinja2:
  base.html    casca (head + header + menu + rodape)
  pagina.html  base + hero + <main class="wrap">, extendido pelas paginas
  partials/    header, menu e os macros reaproveitados entre paginas

Os modulos de rota so montam dados e chamam render(); nenhum deles concatena
HTML. O autoescape esta ligado, entao os formatadores devolvem texto puro.
"""

import datetime
import decimal
import os

import jinja2

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

AMBIENTE = os.getenv("ENV", "local")
# GOOGLE_CLOUD_PROJECT pode vir vazio do entrypoint, por isso o fallback explicito.
PROJETO = (
    os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or "xxx-datalake-hml-01"
)

# SSO por ambiente; local usa o de homologacao
SSO_POR_AMBIENTE = {
    "prd": "https://id.xxx-capital.com/cas/logout/",
    "hml": "https://sso-stg.xxx-tech.dev/cas/logout/",
}
SSO_URL = SSO_POR_AMBIENTE.get(AMBIENTE, SSO_POR_AMBIENTE["hml"])

MENU = [
    {
        "titulo": "Oracle",
        "itens": [
            {"href": "/oracle", "icone": "gauge", "rotulo": "Visão geral"},
            {"href": "/oracle/objetos", "icone": "table-2", "rotulo": "Objetos"},
            {"href": "/oracle/dicionario", "icone": "book-open", "rotulo": "Dicionário"},
            {
                "href": "/oracle/relacionamentos",
                "icone": "share-2",
                "rotulo": "Relacionamentos",
            },
            {"href": "/oracle/grafo", "icone": "network", "rotulo": "Visão Grafo"},
            {"href": "/oracle/mapa", "icone": "orbit", "rotulo": "Mapa semântico"},
            {"href": "/oracle/busca", "icone": "search", "rotulo": "Busca semântica"},
            {"href": "/oracle/orfas", "icone": "unlink", "rotulo": "Órfãs"},
            {"href": "/oracle/amostras", "icone": "scan-search", "rotulo": "Amostras"},
            {"href": "/oracle/indices", "icone": "list-ordered", "rotulo": "Índices"},
            {"href": "/oracle/restricoes", "icone": "shield-check", "rotulo": "Restrições"},
        ],
    },
    {
        "titulo": "Setup",
        "itens": [
            {"href": "/setup/provedores", "icone": "bot", "rotulo": "AI Providers"},
            {"href": "/setup/lote", "icone": "layers", "rotulo": "Lote de descrições"},
            # Mesma pagina, outra tarefa. O ativo do menu casa por href exato, entao
            # setup_lote.py devolve este caminho canonico mesmo com filtro na URL.
            {
                "href": "/setup/lote?tarefa=embedding",
                "icone": "binary",
                "rotulo": "Lote de vetores",
            },
            {
                "href": "/setup/lote?tarefa=mascara",
                "icone": "shield-alert",
                "rotulo": "Lote de sensibilidade",
            },
        ],
    },
    {
        "titulo": "Serviço",
        "itens": [
            {"href": "/health", "icone": "activity", "rotulo": "Health"},
            {"href": "/debug", "icone": "bug", "rotulo": "Debug"},
        ],
    },
]


# --------------------------------------------------------------------------
# Formatacao de valores (registrada como filtro do Jinja)
# --------------------------------------------------------------------------


def eh_numero(valor):
    # NUMERIC do BigQuery chega como Decimal e tambem alinha a direita
    return isinstance(valor, (int, float, decimal.Decimal)) and not isinstance(valor, bool)


def fmt(valor):
    # Milhar com ponto e decimal com virgula, sem depender de locale no container
    if valor is None:
        return "—"
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, datetime.datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, datetime.date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, int):
        return f"{valor:,}".replace(",", ".")
    if isinstance(valor, (float, decimal.Decimal)):
        return f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return str(valor)


def fmt_moeda(valor):
    return "—" if valor is None else f"R$ {fmt(valor)}"


def fmt_moeda_curta(valor):
    # Saldo na casa dos bilhoes nao cabe no card; o valor cheio vai no hint
    if valor is None:
        return "—"
    valor = float(valor)
    for corte, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(valor) >= corte:
            numero = f"{valor / corte:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            return f"R$ {numero} {sufixo}"
    return fmt_moeda(valor)


# --------------------------------------------------------------------------
# Paginacao (compartilhada pelas listagens)
# --------------------------------------------------------------------------


def numeros_visiveis(pagina, paginas, vizinhos=2):
    """Primeira, ultima e as vizinhas da atual; None marca onde entra o '...'."""
    marcadas = {1, paginas}
    marcadas.update(range(max(1, pagina - vizinhos), min(paginas, pagina + vizinhos) + 1))

    sequencia = []
    anterior = 0
    for numero in sorted(marcadas):
        if numero - anterior > 1:
            sequencia.append(None)
        sequencia.append(numero)
        anterior = numero
    return sequencia


def faixa_exibida(pag, linhas):
    """Texto "1-50 de 2.269" do rodape das listagens."""
    total = fmt(pag["total"])
    if not linhas:
        return f"0 de {total}"
    return f"{fmt(pag['primeiro'])}\u2013{fmt(pag['ultimo'])} de {total}"


# --------------------------------------------------------------------------
# Ambiente Jinja2
# --------------------------------------------------------------------------

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    autoescape=jinja2.select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
    # Recarrega o template alterado sem reiniciar o uvicorn (--reload so olha .py)
    auto_reload=True,
)

env.filters["fmt"] = fmt
env.filters["moeda"] = fmt_moeda
env.filters["moeda_curta"] = fmt_moeda_curta

env.globals.update(
    ambiente=AMBIENTE,
    projeto=PROJETO,
    sso_url=SSO_URL,
    menu=MENU,
)


def render(template, titulo, usuario=None, caminho="/", **contexto):
    """Renderiza uma pagina completa (a template extende base.html)."""
    return env.get_template(template).render(
        titulo=titulo, usuario=usuario, caminho=caminho, **contexto
    )
