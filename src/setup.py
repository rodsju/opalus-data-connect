"""Conteudo das rotas /setup: cadastro dos provedores de IA.

As rotas em src/main.py so montam dados e chamam gerar_*(); a regra de negocio
(slug, cifragem, validacao) vive em src/provedores.py.
"""

from . import catalogo, layout, provedores

LISTA = "/setup/provedores"

CAMPOS_LISTA = [
    ("nome", "Nome", False),
    ("slug", "Slug", False),
    ("tipo", "Type", False),
    ("capacidade", "Capability", False),
    ("modelos", "Models", False),
    ("url", "URL", False),
    ("chave", "Key", False),
    ("situacao", "Situação", False),
]


def _aviso(erro):
    return {"motivo": erro.motivo, "detalhe": erro.detalhe}


def gerar_lista(usuario=None, aviso=None):
    try:
        linhas = provedores.listar()
    except catalogo.ConsultaFalhou as falha:
        html = layout.render(
            "erro.html",
            "Não conseguimos ler os provedores",
            usuario,
            LISTA,
            crumb="Setup",
            descricao="O cadastro fica no Postgres do catálogo.",
            alvo=falha.descricao,
            detalhe=str(falha.causa),
            voltar=LISTA,
        )
        return html, 502

    for linha in linhas:
        linha["modelos"] = ", ".join(linha["modelos"])
        # A chave nunca volta para a tela: so os quatro ultimos caracteres
        linha["chave"] = "••••" + linha["chave_final"]
        linha["situacao"] = "ativo" if linha["ativo"] else "inativo"

    colunas = [{"rotulo": rotulo, "num": num} for _, rotulo, num in CAMPOS_LISTA]
    celulas = [
        [
            {
                "valor": linha[chave],
                "num": num,
                **({"href": f"{LISTA}/{linha['slug']}"} if chave == "nome" else {}),
            }
            for chave, _, num in CAMPOS_LISTA
        ]
        for linha in linhas
    ]

    html = layout.render(
        "setup_provedores.html",
        "AI Providers",
        usuario,
        LISTA,
        crumb="Setup",
        descricao="Provedores usados para descrever os campos das tabelas.",
        colunas=colunas,
        linhas=celulas,
        total=len(linhas),
        aviso=aviso,
        senha_ok=_senha_configurada(),
    )
    return html, 200


def _senha_configurada():
    try:
        provedores.senha_mestra()
        return True
    except provedores.ConfiguracaoInvalida:
        return False


def gerar_form(slug=None, usuario=None, aviso=None, valores=None):
    """Formulario de criar (slug=None) ou editar. `valores` repoe o que o usuário
    digitou quando a gravação falhou, para ele não perder o preenchimento."""
    provedor = None
    if slug:
        provedor = provedores.buscar(slug)
        if not provedor:
            return None, 404
        provedor = dict(provedor)
        provedor["modelos"] = ", ".join(provedor["modelos"])

    html = layout.render(
        "setup_provedor_form.html",
        provedor["nome"] if provedor else "Novo provedor",
        usuario,
        LISTA,
        crumb="Setup · AI Providers",
        descricao=(
            "O slug é derivado do nome e não muda depois — as descrições já geradas "
            "apontam para ele."
        ),
        provedor=provedor,
        valores=valores or {},
        tipos=provedores.TIPOS,
        capacidades=provedores.CAPACIDADES,
        aviso=aviso,
        senha_ok=_senha_configurada(),
    )
    return html, 200
