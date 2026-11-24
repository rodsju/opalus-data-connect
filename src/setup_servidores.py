"""Conteudo das rotas /setup/servidores: cadastro dos servidores de origem.

As rotas em src/main.py so montam dados e chamam gerar_*(); a regra de negocio
(validacao, credencial, teste) vive em src/servidores.py.
"""

from . import catalogo, layout, servidores

LISTA = "/setup/servidores"

CAMPOS_LISTA = [
    ("nome", "Nome", False),
    ("tipo", "Tipo", False),
    ("destino", "Destino", False),
    ("perfil_local", "Local", False),
    ("perfil_gcp", "GCP (Cloud Run)", False),
    ("n_esquemas", "Schemas", True),
    ("n_objetos", "Objetos", True),
    ("situacao", "Situação", False),
]


def descrever_senha(servidor, perfil="local"):
    """Como a senha do perfil aparece na tela: a origem, nunca o valor."""
    p = servidores.perfil_de(servidor, perfil)
    if p["senha_fonte"] == "cifrada":
        return "cifrada ••••" + (servidor.get("senha_final") or "")
    return f"{p['senha_fonte']} {p['senha_ref'] or '?'}"


def descrever_perfil(servidor, perfil):
    """"DS_IW · secret atlas-iw-..." ou "não configurado"."""
    usuario = servidores.perfil_de(servidor, perfil)["usuario"]
    if not usuario:
        return "não configurado"
    return f"{usuario} · {descrever_senha(servidor, perfil)}"


def _erro(falha, usuario):
    html = layout.render(
        "erro.html",
        "Não conseguimos ler os servidores",
        usuario,
        LISTA,
        crumb="Setup",
        descricao="O cadastro fica no Postgres do catálogo. Se a mensagem fala de "
        "coluna inexistente, aplique o DDL (make schema, ou docs/gcp-setup.md seção 9).",
        alvo=falha.descricao,
        detalhe=str(falha.causa),
        voltar=LISTA,
    )
    return html, 502


def gerar_lista(usuario=None, aviso=None):
    try:
        linhas = servidores.listar()
    except catalogo.ConsultaFalhou as falha:
        return _erro(falha, usuario)

    for linha in linhas:
        linha["destino"] = f"{linha['host']}:{linha['porta']}/{linha['base']}"
        linha["perfil_local"] = descrever_perfil(linha, "local")
        linha["perfil_gcp"] = descrever_perfil(linha, "gcp")
        linha["situacao"] = "ativo" if linha["ativo"] else "inativo"

    colunas = [{"rotulo": rotulo, "num": num} for _, rotulo, num in CAMPOS_LISTA]
    celulas = [
        [
            {
                "valor": linha[chave],
                "num": num,
                **({"href": f"{LISTA}/{linha['id']}"} if chave == "nome" else {}),
            }
            for chave, _, num in CAMPOS_LISTA
        ]
        for linha in linhas
    ]

    html = layout.render(
        "setup_servidores.html",
        "Servidores",
        usuario,
        LISTA,
        crumb="Setup",
        descricao="Bancos de origem do catálogo: cada objeto aponta para um schema de um servidor.",
        colunas=colunas,
        linhas=celulas,
        total=len(linhas),
        aviso=aviso,
    )
    return html, 200


def contexto_gcp(servidor=None):
    """O que o painel "Conectar no GCP" mostra, com os nomes deste ambiente."""
    projeto = servidores.projeto_gcp() or "<projeto>"
    sa = servidores.sa_runtime() or f"atlas-app-connect@{projeto}.iam.gserviceaccount.com"
    secret = ""
    if servidor and servidor.get("senha_fonte_gcp") == "secret":
        secret = servidor.get("senha_ref_gcp") or ""
    return {
        "no_cloud_run": servidores.no_cloud_run(),
        "projeto": projeto,
        "sa": sa,
        "sa_detectada": bool(servidores.sa_runtime()),
        "secret": secret or "atlas-<origem>-password",
        "host": (servidor or {}).get("host") or "<host>",
        "porta": (servidor or {}).get("porta") or "<porta>",
    }


def gerar_form(servidor_id=None, usuario=None, aviso=None, valores=None, teste=None):
    """Formulario de criar (servidor_id=None) ou editar. `valores` repoe o que o
    usuario digitou quando a gravacao falhou; `teste` e o resultado do botao
    Testar conexao."""
    servidor, lista_esquemas = None, []
    if servidor_id:
        try:
            servidor = servidores.buscar(servidor_id)
            if not servidor:
                return None, 404
            lista_esquemas = servidores.esquemas(servidor_id)
        except catalogo.ConsultaFalhou as falha:
            return _erro(falha, usuario)
        servidor = dict(servidor)

    html = layout.render(
        "setup_servidor_form.html",
        servidor["nome"] if servidor else "Novo servidor",
        usuario,
        LISTA,
        crumb="Setup · Servidores",
        descricao=(
            "Tipo, host, porta e base identificam o servidor. A senha nunca volta "
            "para a tela: só a origem dela."
        ),
        servidor=servidor,
        # Nao `esquemas`: esse nome e o do seletor do cabecalho (layout.render)
        schemas_do_servidor=lista_esquemas,
        valores=valores or {},
        tipos=servidores.TIPOS,
        portas=servidores.PORTA_PADRAO,
        perfis={
            nome: {
                "rotulo": cfg["rotulo"],
                "fontes": [(f, servidores.ROTULO_FONTE[f]) for f in cfg["fontes"]],
            }
            for nome, cfg in servidores.PERFIS.items()
        },
        perfil_atual=servidores.perfil_atual(),
        aviso=aviso,
        teste=teste,
        gcp=contexto_gcp(servidor),
    )
    return html, 200
