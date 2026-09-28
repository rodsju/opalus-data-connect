"""Conteudo das rotas /setup/lote: selecao das tabelas e progresso do lote."""

from . import catalogo, ia, layout, lote as lote_mod, provedores

LISTA = "/setup/lote"


def _pagina_erro(falha, usuario, caminho):
    html = layout.render(
        "erro.html",
        "Não conseguimos ler os lotes",
        usuario,
        caminho,
        crumb="Setup",
        descricao="O lote fica no Postgres do catálogo.",
        alvo=getattr(falha, "descricao", "lote"),
        detalhe=str(getattr(falha, "causa", falha)),
        voltar=caminho,
    )
    return html, 502


# Cada tarefa tem seu titulo, sua capacidade de provedor e sua coluna de situacao.
TAREFA = {
    "descricao": {
        "titulo": "Lote de descrições",
        "caminho": LISTA,
        "capacidade": "llm",
        "coluna": "Descrição",
        "feito": "descrita",
        "campo": "descrita",
        "rotulo": "descrições",
        "confirmacao": "Isso vai gerar {n} descrições. Confirma?",
        "descricao": (
            "Seleciona tabelas por filtro e dispara a geração em massa. O lote roda "
            "fora da aplicação e continua mesmo se você fechar esta página."
        ),
    },
    "embedding": {
        "titulo": "Lote de vetores",
        "caminho": f"{LISTA}?tarefa=embedding",
        "capacidade": "embedding",
        "coluna": "Vetor",
        "feito": "vetorizada",
        "campo": "vetorizada",
        "rotulo": "vetores",
        # Vetorizar nao gasta token de saida: a confirmacao fala de volume, nao de custo.
        "confirmacao": "Isso vai vetorizar {n} tabelas e os campos de cada uma. Confirma?",
        "descricao": (
            "Vetoriza a descrição já gerada de cada tabela e de cada campo. Tabela "
            "sem descrição não tem texto para vetorizar — filtre por “só sem vetor”."
        ),
    },
    "mascara": {
        "titulo": "Lote de sensibilidade",
        "caminho": f"{LISTA}?tarefa=mascara",
        "capacidade": "llm",
        "coluna": "Avaliada",
        "feito": "classificada",
        "campo": "classificada",
        "rotulo": "sensibilidade",
        # O tamanho do pacote sai da constante: escrito a mao, ele divergiu no
        # mesmo dia em que a medicao baixou de 100 para 50.
        "confirmacao": (
            "Isso vai classificar as colunas de {n} tabelas, em pacotes de "
            f"{ia.COLUNAS_POR_PACOTE} campos por chamada. Confirma?"
        ),
        "descricao": (
            "A IA lê a descrição já gerada de cada campo e diz se ele guarda dado "
            "sensível. É inventário: nada passa a ser ocultado por causa da marca. "
            "Campo sem descrição não é avaliado — filtre por “só com coluna não "
            "avaliada”."
        ),
    },
}


def gerar_selecao(ativos=(), termo="", paralelismo=4, usuario=None, aviso=None,
                  tarefa="descricao"):
    """Lista filtrada + formulario de disparo."""
    config = TAREFA[tarefa]
    try:
        linhas, total = lote_mod.candidatas(ativos, termo, tarefa=tarefa)
        pares = provedores.disponiveis(config["capacidade"])
        aberto = lote_mod.em_andamento(tarefa)
        recentes = lote_mod.listar()
    except (catalogo.ConsultaFalhou, provedores.ConfiguracaoInvalida) as falha:
        if isinstance(falha, provedores.ConfiguracaoInvalida):
            pares, aberto, recentes = [], None, []
            linhas, total = [], 0
            aviso = aviso or {"motivo": falha.motivo, "detalhe": falha.detalhe}
        else:
            return _pagina_erro(falha, usuario, LISTA)

    html = layout.render(
        "setup_lote.html",
        config["titulo"],
        usuario,
        config["caminho"],
        crumb="Setup",
        descricao=config["descricao"],
        linhas=linhas,
        total=total,
        mostrando=len(linhas),
        filtros=[
            {"param": param, "rotulo": rotulo, "ativo": chave in ativos}
            for chave, param, rotulo, _ in lote_mod.FILTROS
        ],
        termo=termo,
        paralelismo=paralelismo,
        pares=pares,
        tarefa=tarefa,
        coluna_feito=config["coluna"],
        campo_feito=config["campo"],
        rotulo_feito=config["feito"],
        confirmacao=config["confirmacao"],
        # Rotulo de cada tarefa, para a tabela de lotes recentes nao precisar de
        # um ternario que so sabe contar ate dois.
        rotulos={chave: cfg["rotulo"] for chave, cfg in TAREFA.items()},
        estimativa=lote_mod.estimativa(total, paralelismo, tarefa),
        aberto=aberto,
        recentes=recentes,
        aviso=aviso,
    )
    return html, 200


def gerar_progresso(lote_id, usuario=None, aviso=None):
    try:
        lote = lote_mod.buscar(lote_id)
        if not lote:
            return None, 404
        andamento = lote_mod.progresso(lote_id)
        problemas = lote_mod.falhas(lote_id)
    except catalogo.ConsultaFalhou as falha:
        return _pagina_erro(falha, usuario, f"{LISTA}/{lote_id}")

    restantes = andamento["pendente"] + andamento["rodando"]
    html = layout.render(
        "setup_lote_progresso.html",
        f"Lote #{lote_id}",
        usuario,
        TAREFA[lote["tarefa"]]["caminho"],
        crumb=f"Setup · {TAREFA[lote['tarefa']]['titulo']}",
        descricao=(
            f"{TAREFA[lote['tarefa']]['titulo']} · {lote['provedor']} · {lote['modelo']} · "
            f"{lote['paralelismo']} em paralelo"
        ),
        lote=lote,
        andamento=andamento,
        falhas=problemas,
        # Enquanto roda, a pagina se recarrega sozinha; ao terminar, para
        recarregar=lote["status"] in ("pendente", "rodando"),
        restante=lote_mod.estimativa(
            restantes, lote["paralelismo"], lote["tarefa"]
        )["duracao"],
        aviso=aviso,
    )
    return html, 200
