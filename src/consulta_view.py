"""Conteudo das rotas /oracle/consulta: editor, sugestao da IA, resultado e historico.

A regra (checagem, execucao travada, mascara, auditoria, prompt) vive em
src/consulta.py. Esta pagina respeita o schema do cabecalho: e nele que a query roda.
"""

from . import catalogo, consulta, esquemas, layout, provedores

CAMINHO = "/oracle/consulta"


def gerar(usuario=None, sql="", pedido="", tabelas="", aba="sql", provedor="",
          sugestao=None, resultado=None, aviso=None, modo="sql"):
    email = usuario["email"] if usuario else None
    esquema = esquemas.atual()
    try:
        historico = consulta.historico(email)
        cobertura = consulta.cobertura(esquema["id"]) if esquema else None
    except catalogo.ConsultaFalhou as falha:
        historico, cobertura = [], None
        aviso = aviso or {"motivo": "Não conseguimos ler o histórico",
                          "detalhe": str(getattr(falha, "causa", falha))}
    try:
        pares = provedores.disponiveis()
    except provedores.ConfiguracaoInvalida:
        pares = []

    cards = []
    if resultado:
        cards = [
            {"rotulo": "Linhas", "valor": layout.fmt(len(resultado["linhas"])),
             "hint": f"cortado em {consulta.LIMITE}" if resultado["truncada"] else "todas"},
            {"rotulo": "Colunas", "valor": layout.fmt(len(resultado["colunas"])), "hint": ""},
            {"rotulo": "Tempo", "valor": f"{resultado['ms']} ms", "hint": ""},
            {"rotulo": "Mascaradas", "valor": layout.fmt(len(resultado["mascaradas"])),
             "hint": "colunas sensíveis" if resultado["mascaradas"] else ""},
        ]

    html = layout.render(
        "oracle_consulta.html",
        "Assistente de consulta",
        usuario,
        CAMINHO,
        crumb="Fontes de dados",
        descricao=(
            f"Consulta ao vivo no schema {esquemas.rotulo(esquema)}." if esquema
            else "Escolha um schema no cabeçalho para consultar."
        ),
        esquema=esquema,
        sql=sql,
        pedido=pedido,
        tabelas=tabelas,
        aba=aba,
        modo=modo,
        provedor=provedor,
        pares=pares,
        sugestao=sugestao,
        resultado=resultado,
        cards=cards,
        historico=historico,
        cobertura=cobertura,
        limite=consulta.LIMITE,
        tempo_maximo=consulta.TEMPO_MAXIMO_MS // 1000,
        mascara=consulta.MASCARA,
        aviso=aviso,
    )
    return html, 200
