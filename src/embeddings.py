"""Vetores de embedding das descricoes geradas por IA.

Este modulo e o USO; src/provedores.py e a CONFIGURACAO -- a mesma divisao de
src/ia.py, que escreve o texto que aqui vira vetor.

Um texto, um vetor, sem chunking: rotulo + resumo + funcao viram o vetor da
tabela, e a descricao de cada campo vira o vetor da coluna. Os textos sao curtos
e cabem inteiros na janela de qualquer modelo de embedding -- por isso nada aqui
lembra o pipeline de chunk/overlap de um RAG sobre documento.

Onde o vetor mora: catalogo.objeto.embedding e catalogo.coluna.embedding. Como a
descricao do campo nasce dentro do jsonb descricao_ia.campos e o vetor precisa de
um texto por linha, vetorizar_objeto() primeiro materializa esse texto em
catalogo.coluna.descricao_ia.
"""

import hashlib
import logging
import random
import time

from . import catalogo, provedores

logger = logging.getLogger(__name__)

# Textos por chamada. O limite real da API e bem maior (a OpenAI aceita 2048),
# mas lote grande demais transforma um 429 no fim da fila em retrabalho caro.
LOTE = 64

# Tentativas por chamada, com espera exponencial. A referencia de onde este
# modulo saiu (~/apps/app-aidocs-vert/src/vectors.py) nao tem retry nenhum, e num
# lote de 2 mil tabelas o primeiro 429 derrubaria o item.
TENTATIVAS = 4
ESPERA_BASE = 2.0


class EmbutirFalhou(Exception):
    """Mesmo contrato de ia.GeracaoFalhou: motivo curto + detalhe acionavel."""

    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


def vetor_para_pg(vetor):
    """[0.1, 0.2] -> "[0.1,0.2]", o literal que o cast ::vector aceita.

    Evita a dependencia do pacote pgvector so para tipar o parametro no psycopg.
    """
    return "[" + ",".join(repr(float(x)) for x in vetor) + "]"


def hash_texto(texto):
    """sha256 do texto de origem; alimenta embedding_hash.

    E o que torna barato re-rodar o lote: texto que nao mudou nao volta para a
    API.
    """
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def texto_do_objeto(nome, descricao):
    """O que representa a tabela. O nome entra porque e ele que o usuario digita."""
    partes = [nome, descricao.get("rotulo"), descricao.get("resumo"), descricao.get("funcao")]
    return "\n".join(parte.strip() for parte in partes if parte and parte.strip())


def texto_da_coluna(objeto_nome, coluna_nome, descricao):
    """Campo isolado diz pouco: "Data de inicio" existe em dezenas de tabelas.

    O nome da tabela e o da coluna entram como contexto para o vetor distinguir.
    """
    return f"{objeto_nome}.{coluna_nome}: {descricao.strip()}"


# --------------------------------------------------------------------------
# Chamada da API
# --------------------------------------------------------------------------


def _um_lote(cliente, textos, prov):
    """Uma chamada, com retry. Devolve os vetores na ordem dos textos."""
    import openai

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = cliente.embeddings.create(model=prov.modelo, input=textos)
            break
        except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError,
                openai.InternalServerError) as falha:
            if tentativa == TENTATIVAS:
                raise EmbutirFalhou(
                    "O provedor de embeddings não respondeu",
                    f"{type(falha).__name__} em {TENTATIVAS} tentativas: {falha}",
                ) from falha
            espera = ESPERA_BASE ** tentativa + random.uniform(0, 1)
            logger.warning(
                "embeddings: %s na tentativa %s de %s, repetindo em %.1fs",
                type(falha).__name__, tentativa, TENTATIVAS, espera,
            )
            time.sleep(espera)
        except openai.APIStatusError as falha:
            raise EmbutirFalhou(
                "O provedor de embeddings recusou a chamada",
                f"HTTP {falha.status_code}: {falha}",
            ) from falha

    # A API nao promete devolver na ordem em que mandamos; o campo index e quem
    # promete. Ignorar isso associaria silenciosamente o vetor errado a cada texto.
    dados = sorted(resposta.data, key=lambda item: item.index)
    vetores = [item.embedding for item in dados]
    if len(vetores) != len(textos):
        raise EmbutirFalhou(
            "O provedor devolveu uma quantidade inesperada de vetores",
            f"esperados {len(textos)}, recebidos {len(vetores)}.",
        )
    return vetores


def embutir(textos, prov):
    """Vetoriza a lista inteira, em lotes. Devolve (vetores, dimensao)."""
    if prov.tipo != "openai":
        raise EmbutirFalhou(
            f"O provedor '{prov.nome}' não serve para embeddings",
            "A API de embeddings segue o formato OpenAI; a Anthropic não tem uma. "
            "Cadastre o provedor com tipo 'openai' em Setup › AI Providers.",
        )
    if not textos:
        return [], None

    import openai

    cliente = openai.OpenAI(api_key=prov.chave, base_url=prov.url or None)
    vetores = []
    for inicio in range(0, len(textos), LOTE):
        vetores.extend(_um_lote(cliente, textos[inicio:inicio + LOTE], prov))

    dimensoes = {len(vetor) for vetor in vetores}
    if len(dimensoes) > 1:
        raise EmbutirFalhou(
            "O provedor devolveu vetores de dimensões diferentes",
            f"dimensões recebidas: {sorted(dimensoes)}.",
        )
    return vetores, dimensoes.pop()


# --------------------------------------------------------------------------
# Leitura e gravacao
# --------------------------------------------------------------------------

SQL_DESCRICAO = """
SELECT o.id, o.nome, o.embedding_hash, o.embedding_modelo,
       d.rotulo, d.resumo, d.funcao, d.campos
  FROM catalogo.objeto o
  JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 WHERE o.id = %s
"""

# Materializa a descricao do campo, hoje so dentro do jsonb, na linha da coluna.
# O casamento por nome e o mesmo do LATERAL de catalogo.vw_dicionario.
SQL_SINCRONIZAR_CAMPOS = """
UPDATE catalogo.coluna c
   SET descricao_ia = campo.descricao
  FROM catalogo.descricao_ia d
  CROSS JOIN LATERAL jsonb_to_recordset(d.campos) AS campo(coluna text, descricao text)
 WHERE d.objeto_id = %s
   AND c.objeto_id = d.objeto_id
   AND c.nome = campo.coluna
   AND c.descricao_ia IS DISTINCT FROM campo.descricao
"""

# A outra metade do sincronismo: campo que SAIU do jsonb tem de sair da coluna
# tambem. Sem isto o UPDATE acima -- que so alcanca linha com par no jsonb --
# deixaria para tras o texto antigo E o vetor dele, e a busca semantica
# continuaria devolvendo a coluna por uma descricao que ninguem ve mais na tela
# (catalogo.vw_dicionario le o jsonb). O orfao so ficou alcancavel quando a API
# passou a aceitar remocao de campo, mas a regeneracao por IA sempre pode
# devolver um campo a menos.
SQL_LIMPAR_SUMIDOS = """
UPDATE catalogo.coluna c
   SET descricao_ia = NULL, embedding = NULL, embedding_modelo = NULL,
       embedding_dim = NULL, embedding_hash = NULL, embedding_em = NULL
  FROM catalogo.descricao_ia d
 WHERE d.objeto_id = %s
   AND c.objeto_id = d.objeto_id
   AND c.descricao_ia IS NOT NULL
   AND NOT EXISTS (
       SELECT 1 FROM jsonb_array_elements(d.campos) campo
        WHERE campo->>'coluna' = c.nome
   )
"""

SQL_COLUNAS = """
SELECT id, nome, descricao_ia, embedding_hash, embedding_modelo
  FROM catalogo.coluna
 WHERE objeto_id = %s
   AND descricao_ia IS NOT NULL
   AND descricao_ia <> ''
 ORDER BY posicao
"""

SQL_GRAVAR_OBJETO = """
UPDATE catalogo.objeto
   SET embedding = %s::vector, embedding_modelo = %s, embedding_dim = %s,
       embedding_hash = %s, embedding_em = now()
 WHERE id = %s
"""

# Um UPDATE para a tabela inteira: catalogo.executar abre uma conexao por
# chamada, e uma tabela larga tem centenas de campos.
SQL_GRAVAR_COLUNAS = """
UPDATE catalogo.coluna c
   SET embedding = v.vetor::vector, embedding_modelo = %s, embedding_dim = %s,
       embedding_hash = v.hash, embedding_em = now()
  FROM (SELECT unnest(%s::bigint[]) AS id,
               unnest(%s::text[])   AS vetor,
               unnest(%s::text[])   AS hash) v
 WHERE c.id = v.id
"""


def _pendentes(linhas, textos_por_id, modelo):
    """Quem precisa ir para a API: texto novo, ou o mesmo texto com outro modelo.

    Comparar tambem o modelo importa porque vetor de modelos diferentes nao se
    compara -- o operador <=> recusa dimensoes distintas.
    """
    return [
        linha for linha in linhas
        if linha["embedding_hash"] != hash_texto(textos_por_id[linha["id"]])
        or linha["embedding_modelo"] != modelo
    ]


def vetorizar_objeto(objeto_id, par=None):
    """Vetoriza a tabela e os campos descritos. Devolve os metadados do que foi feito.

    `par` e o "slug::modelo" escolhido na tela; sem ele usa o primeiro provedor
    de embedding ativo.
    """
    prov = provedores.escolher(par, capacidade="embedding")

    objeto = catalogo.um(SQL_DESCRICAO, (objeto_id,), "descrição para vetorizar")
    if not objeto:
        raise EmbutirFalhou(
            "Esta tabela ainda não tem descrição de IA",
            "Gere a descrição primeiro: sem texto não há o que vetorizar.",
        )

    catalogo.executar(SQL_SINCRONIZAR_CAMPOS, (objeto_id,), f"campos de {objeto['nome']}")
    catalogo.executar(SQL_LIMPAR_SUMIDOS, (objeto_id,), f"campos sumidos de {objeto['nome']}")
    colunas = catalogo.consultar(SQL_COLUNAS, (objeto_id,), f"colunas de {objeto['nome']}")

    texto_objeto = texto_do_objeto(objeto["nome"], objeto)
    textos_coluna = {
        coluna["id"]: texto_da_coluna(objeto["nome"], coluna["nome"], coluna["descricao_ia"])
        for coluna in colunas
    }

    objeto_pendente = bool(
        _pendentes([objeto], {objeto["id"]: texto_objeto}, prov.modelo)
    )
    colunas_pendentes = _pendentes(colunas, textos_coluna, prov.modelo)

    if not objeto_pendente and not colunas_pendentes:
        logger.info("%s ja esta vetorizado com %s, nada a fazer",
                    objeto["nome"], prov.modelo)
        return {"provedor": prov.slug, "modelo": prov.modelo,
                "objeto": False, "colunas": 0, "dimensao": None}

    textos = ([texto_objeto] if objeto_pendente else []) + [
        textos_coluna[coluna["id"]] for coluna in colunas_pendentes
    ]
    logger.info("vetorizando %s via %s (%s): %s textos",
                objeto["nome"], prov.slug, prov.modelo, len(textos))

    vetores, dimensao = embutir(textos, prov)

    if objeto_pendente:
        catalogo.executar(
            SQL_GRAVAR_OBJETO,
            (vetor_para_pg(vetores[0]), prov.modelo, dimensao,
             hash_texto(texto_objeto), objeto["id"]),
            f"vetor de {objeto['nome']}",
        )

    if colunas_pendentes:
        vetores_coluna = vetores[1:] if objeto_pendente else vetores
        catalogo.executar(
            SQL_GRAVAR_COLUNAS,
            (
                prov.modelo,
                dimensao,
                [coluna["id"] for coluna in colunas_pendentes],
                [vetor_para_pg(vetor) for vetor in vetores_coluna],
                [hash_texto(textos_coluna[coluna["id"]]) for coluna in colunas_pendentes],
            ),
            f"vetores das colunas de {objeto['nome']}",
        )

    return {
        "provedor": prov.slug,
        "modelo": prov.modelo,
        "objeto": objeto_pendente,
        "colunas": len(colunas_pendentes),
        "dimensao": dimensao,
    }
