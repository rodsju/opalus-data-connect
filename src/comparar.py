"""Conteudo das rotas /oracle/comparar: selecao, resultado e historico.

A regra (diferenca, prompt, gravacao) vive em src/comparacao.py. A pagina e
transversal aos schemas: ignora o pre-filtro do cabecalho, porque comparar
schemas e justamente o ponto.
"""

from . import catalogo, comparacao, layout, provedores

CAMINHO = "/oracle/comparar"


def _pagina_erro(falha, usuario):
    html = layout.render(
        "erro.html",
        "Não conseguimos montar a comparação",
        usuario,
        CAMINHO,
        crumb="Oracle",
        descricao="A comparação lê o catálogo no Postgres.",
        alvo=getattr(falha, "descricao", "comparação"),
        detalhe=str(getattr(falha, "causa", falha)),
        voltar=CAMINHO,
    )
    return html, 502


def gerar_selecao(nome="", termo="", selecionados=(), usuario=None, aviso=None):
    """Seletor: os schemas que tem `nome` (ja marcados), a busca livre e o historico."""
    try:
        escolhidos = comparacao.resumo_objetos(list(selecionados))
        mesmos = comparacao.candidatos(nome) if nome.strip() else []
        achados = comparacao.buscar(termo) if termo.strip() else []
        historico = comparacao.listar()
    except catalogo.ConsultaFalhou as falha:
        return _pagina_erro(falha, usuario)

    # Uma lista so, sem repetir: o que ja estava escolhido, depois os do mesmo
    # nome (marcados), depois a busca (desmarcados)
    vistos, opcoes = set(), []
    for grupo, marcado in ((escolhidos, True), (mesmos, True), (achados, False)):
        for objeto in grupo:
            if objeto["id"] in vistos:
                continue
            vistos.add(objeto["id"])
            opcoes.append({**objeto, "marcado": marcado})

    html = layout.render(
        "oracle_comparar.html",
        "Comparar tabelas",
        usuario,
        CAMINHO,
        crumb="Oracle",
        descricao=(
            "Compare a mesma tabela entre schemas, ou tabelas quaisquer: a diferença "
            "estrutural sai na hora, e a IA explica o que ela significa."
        ),
        nome=nome,
        termo=termo,
        opcoes=opcoes,
        nome_sem_resultado=bool(nome.strip()) and not mesmos,
        historico=historico,
        minimo=comparacao.MINIMO,
        maximo=comparacao.MAXIMO,
        aviso=aviso,
    )
    return html, 200


def gerar_resultado(ids, usuario=None, aviso=None):
    try:
        objetos = comparacao.carregar(ids)
        gravada = comparacao.buscar_gravada(ids)
    except catalogo.ConsultaFalhou as falha:
        return _pagina_erro(falha, usuario)
    except comparacao.ComparacaoInvalida as falha:
        return gerar_selecao(selecionados=ids, usuario=usuario,
                             aviso={"motivo": falha.motivo, "detalhe": falha.detalhe})

    dif = comparacao.diferenca(objetos)
    try:
        pares = provedores.disponiveis()
    except provedores.ConfiguracaoInvalida as erro:
        pares = []
        aviso = aviso or {"motivo": erro.motivo, "detalhe": erro.detalhe}

    totais = dif["totais"]
    html = layout.render(
        "oracle_comparacao.html",
        "Comparação",
        usuario,
        CAMINHO,
        crumb="Oracle · Comparar",
        descricao=" × ".join(o["rotulo"] for o in objetos),
        objetos=objetos,
        ids=",".join(str(o["id"]) for o in objetos),
        dif=dif,
        texto_estado=comparacao.texto_estado,
        cards=[
            {"rotulo": "Colunas", "valor": layout.fmt(totais["colunas"]),
             "hint": "união das tabelas"},
            {"rotulo": "Iguais em todas", "valor": layout.fmt(totais["iguais"]), "hint": ""},
            {"rotulo": "Divergentes", "valor": layout.fmt(totais["divergentes"]),
             "hint": "tipo, nulidade ou PK"},
            {"rotulo": "Ausentes em alguma", "valor": layout.fmt(totais["ausentes"]),
             "hint": ""},
        ],
        ia=gravada,
        ia_vencida=comparacao.vencida(gravada, objetos),
        provedores=pares,
        aviso=aviso,
    )
    return html, 200
