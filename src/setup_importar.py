"""Conteudo das rotas /setup/importar: disparo e progresso da importacao.

A regra (validacao, disparo, cancelamento) vive em src/importacao.py.
"""

from . import catalogo, importacao, layout

LISTA = "/setup/importar"

DESCRICAO = (
    "Lê o dicionário do schema de origem (colunas, chaves, índices, comentários, "
    "contagens e amostras) e grava no catálogo. É o mesmo mapeador do make catalogo."
)


def _pagina_erro(falha, usuario, caminho):
    html = layout.render(
        "erro.html",
        "Não conseguimos ler as importações",
        usuario,
        caminho,
        crumb="Setup",
        descricao="A importação fica no Postgres do catálogo.",
        alvo=getattr(falha, "descricao", "importacao"),
        detalhe=str(getattr(falha, "causa", falha)),
        voltar=LISTA,
    )
    return html, 502


def gerar_form(usuario=None, aviso=None, sucesso=None, valores=None):
    try:
        importacao.marcar_sem_sinal()
        origens = importacao.esquemas_oracle()
        aberta = importacao.em_andamento()
        recentes = importacao.listar()
    except catalogo.ConsultaFalhou as falha:
        return _pagina_erro(falha, usuario, LISTA)

    pronto, motivo = importacao.disponivel()
    html = layout.render(
        "setup_importar.html",
        "Importar dados",
        usuario,
        LISTA,
        crumb="Setup",
        descricao=DESCRICAO,
        origens=origens,
        modos=importacao.MODOS,
        valores=valores or {},
        aberta=aberta,
        recentes=recentes,
        pronto=pronto,
        motivo=motivo,
        onde=importacao.onde_roda(),
        timeout_maximo=importacao.TIMEOUT_MAXIMO,
        aviso=aviso,
        sucesso=sucesso,
    )
    return html, 200


def gerar_progresso(importacao_id, usuario=None, aviso=None):
    try:
        importacao.marcar_sem_sinal()
        imp = importacao.buscar(importacao_id)
    except catalogo.ConsultaFalhou as falha:
        return _pagina_erro(falha, usuario, f"{LISTA}/{importacao_id}")
    if not imp:
        return None, 404

    ativa = imp["status"] in ("pendente", "rodando")
    html = layout.render(
        "setup_importar_progresso.html",
        f"Importação #{importacao_id}",
        usuario,
        LISTA,
        crumb="Setup · Importar dados",
        descricao=(
            f"{importacao.MODOS[imp['modo']]} · {imp['servidor']} · {imp['esquema']}"
        ),
        imp=imp,
        percentual=importacao.percentual(imp),
        parametros=sorted((k, v) for k, v in imp["parametros"].items() if v not in (None, False)),
        recarregar=ativa,
        ativa=ativa,
        aviso=aviso,
    )
    return html, 200
