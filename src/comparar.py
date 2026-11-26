"""Conteudo das rotas /oracle/comparar: selecao, resultado e historico.

A regra (diferenca, prompt, gravacao) vive em src/comparacao.py. A pagina e
transversal aos schemas: ignora o pre-filtro do cabecalho, porque comparar
schemas e justamente o ponto.
"""

from . import catalogo, comparacao, esquemas, layout, lote, provedores

CAMINHO = "/oracle/comparar"
CAMINHO_LOTE = "/oracle/comparar/lote"


def _pagina_erro(falha, usuario):
    html = layout.render(
        "erro.html",
        "Não conseguimos montar a comparação",
        usuario,
        CAMINHO,
        crumb="Fontes de dados",
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
        crumb="Fontes de dados",
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
        crumb="Fontes de dados · Comparar",
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


def gerar_lote(base_id=None, alvos=None, termo="", so_sem=False, paralelismo=1,
               usuario=None, aviso=None):
    """Schema base contra os outros: um conjunto por tabela, com a situacao de cada um.

    `alvos` None e "primeira visita": todos os outros schemas entram. Lista vazia
    e o usuario ter desmarcado tudo.
    """
    try:
        lista = esquemas.listar()
        validos = {e["id"] for e in lista}
        if base_id not in validos:
            base_id = esquemas.atual_id() if esquemas.atual_id() in validos else (
                lista[0]["id"] if lista else None)
        if alvos is None:
            alvos = [e["id"] for e in lista if e["id"] != base_id]
        alvos = [a for a in alvos if a in validos and a != base_id]
        conjuntos = comparacao.grupos(base_id, alvos, termo) if base_id else []
        pares = provedores.disponiveis()
        aberto = lote.em_andamento("comparacao")
    except provedores.ConfiguracaoInvalida as falha:
        pares, aberto = [], None
        aviso = aviso or {"motivo": falha.motivo, "detalhe": falha.detalhe}
    except catalogo.ConsultaFalhou as falha:
        return _pagina_erro(falha, usuario)

    contagem = {chave: 0 for chave in comparacao.SITUACOES}
    for conjunto in conjuntos:
        contagem[conjunto["situacao"]] += 1
    visiveis = [c for c in conjuntos if not so_sem or c["situacao"] in ("sem", "vencida")]

    html = layout.render(
        "oracle_comparar_lote.html",
        "Comparar em lote",
        usuario,
        CAMINHO_LOTE,
        crumb="Fontes de dados · Comparar",
        descricao=(
            "Escolha o schema base: cada tabela dele é comparada com a de mesmo nome "
            "nos outros schemas. Cada tabela é um conjunto, e os conjuntos marcados "
            "entram numa fila, um por vez."
        ),
        esquemas_lista=lista,
        base_id=base_id,
        alvos=set(alvos),
        termo=termo,
        so_sem=so_sem,
        conjuntos=visiveis,
        total=len(conjuntos),
        contagem=contagem,
        situacoes=comparacao.SITUACOES,
        paralelismo=paralelismo,
        pares=pares,
        aberto=aberto,
        estimativa=lote.estimativa(
            contagem["sem"] + contagem["vencida"], paralelismo, "comparacao"
        ),
        aviso=aviso,
    )
    return html, 200
