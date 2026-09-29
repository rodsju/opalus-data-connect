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
        "titulo": "Reports",
        "itens": [
            {"href": "/reports/faturamento", "icone": "receipt", "rotulo": "Faturamento"},
            {"href": "/reports/glosa-planilha", "icone": "sheet", "rotulo": "Glosa (xml/planilha)"},
            {"href": "/reports/glosa-motivos", "icone": "tags", "rotulo": "Motivos de glosa"},
            {"href": "/reports/glosa-iw", "icone": "shield-x", "rotulo": "Glosa IW"},
            {"href": "/reports/orcamentos", "icone": "clipboard-list", "rotulo": "Orçamentos"},
            {"href": "/reports/ocupacao", "icone": "bed", "rotulo": "Ocupação"},
            {"href": "/reports/auditoria", "icone": "scale", "rotulo": "Auditoria de contas"},
            {"href": "/reports/blocos", "icone": "layout-grid", "rotulo": "Blocos de relatório"},
        ],
    },
    {
        "titulo": "Consultas",
        "itens": [
            {"href": "/consultas/faturas", "icone": "receipt", "rotulo": "Faturas"},
            {"href": "/consultas/conta-paciente", "icone": "file-stack", "rotulo": "Conta do paciente"},
            {"href": "/consultas/glosas", "icone": "list-x", "rotulo": "Glosas"},
            {"href": "/consultas/pre-auditoria", "icone": "scan-search", "rotulo": "Pré-auditoria"},
            {"href": "/consultas/orcamentos", "icone": "clipboard-check", "rotulo": "Orçamentos"},
            {"href": "/consultas/pacientes", "icone": "bed", "rotulo": "Pacientes em atendimento"},
        ],
    },
    {
        "titulo": "Conciliação",
        "itens": [
            {"href": "/conciliacao/tiss", "icone": "file-code-2", "rotulo": "Retornos TISS (xml)"},
            {"href": "/conciliacao/cargas", "icone": "upload", "rotulo": "Cargas (planilha)"},
            {"href": "/conciliacao/glosa-erp", "icone": "git-compare-arrows", "rotulo": "Qualidade do cruzamento"},
            {"href": "/conciliacao/premissas", "icone": "sliders-horizontal", "rotulo": "Premissas"},
            {"href": "/conciliacao/regras", "icone": "function-square", "rotulo": "Regras da planilha"},
        ],
    },
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


def fmt_pct(valor, casas=1):
    if valor is None:
        return "—"
    return f"{float(valor):,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".") + "%"


def fmt_valor(valor, formato):
    """Formata pelo nome usado nos cards dos /reports (moeda_curta, pct, int...)."""
    if formato == "moeda_curta":
        return fmt_moeda_curta(valor)
    if formato == "moeda":
        return fmt_moeda(valor)
    if formato == "pct":
        return fmt_pct(valor)
    if formato == "int":
        return fmt(None if valor is None else int(round(float(valor))))
    return fmt(valor)


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
env.filters["pct"] = fmt_pct
env.filters["valor"] = fmt_valor

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
