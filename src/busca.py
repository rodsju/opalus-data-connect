"""Busca semantica sobre os vetores do catalogo.

Este modulo e a CONSULTA; src/oracle.py monta a pagina -- a mesma divisao de
src/grafo.py e oracle.gerar_grafo.

Por que o ranking nao e so cosseno. Medindo 300 campos tomados ao acaso deste
catalogo, dois campos SEM relacao nenhuma ja pontuam:

    minimo 0.155 | media 0.456 | p95 0.637 | maximo 0.975

    -- a consulta que mede, para refazer quando trocar de modelo:
    -- WITH amostra AS (SELECT embedding v FROM catalogo.coluna
    --                   WHERE embedding IS NOT NULL ORDER BY random() LIMIT 300),
    --      a AS (SELECT v, row_number() OVER () r FROM amostra)
    -- SELECT avg(1-(x.v <=> y.v)) FROM a x JOIN a y ON x.r < y.r;

Disso vem o desenho todo:

1. Cosseno cru engana. 0.65 parece bom e e ruido, entao a tela nao mostra o
   cosseno: mostra uma relevancia reescalada sobre essa linha de base.
2. So semantica erra o obvio -- quem digita TDPACIENTE quer aquela tabela em
   primeiro lugar. Dai o reforco lexical somado ao cosseno.

Custo: cada busca e uma chamada paga de embedding para vetorizar o termo. Por
isso nao ha paginacao -- paginar re-embutiria a consulta a cada pagina. O top K
ocupa esse lugar.
"""

import logging
import time
import unicodedata

from . import catalogo, embeddings, provedores

logger = logging.getLogger(__name__)

ESCOPOS = ("tabelas", "campos", "ambos")

# O cosseno manda; o lexical desempata e resgata a busca por nome exato.
PESO_COS = 0.85
PESO_LEX = 0.15

# Campo que casa promove a tabela dele, mas vale um pouco menos do que a
# descricao da propria tabela ter casado.
PESO_EVIDENCIA = 0.9

# Quantos campos mostrar como evidencia de cada tabela, no escopo "ambos"
EVIDENCIAS = 3

# Token menor que isto e ruido lexical ("de", "da", "id")
MINIMO_TOKEN = 3

# Similaridade media entre vetores sem relacao, POR MODELO -- e o zero da escala
# que a tela mostra. Trocar de modelo EXIGE remedir com a consulta do topo: a
# linha de base e propria de cada modelo, nao do catalogo.
LINHA_DE_BASE = {"qwen/qwen3-embedding-8b": 0.456}


# --------------------------------------------------------------------------
# Ranking (puro -- e o que os testes cobrem)
# --------------------------------------------------------------------------


def sem_acento(texto):
    """"internação" -> "INTERNACAO". Os nomes vindos do Oracle sao ASCII maiusculo,
    e o Postgres daqui nao tem a extensao unaccent -- entao quem se ajusta e o termo."""
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return base.upper()


def tokens(termo):
    """Palavras uteis do termo, normalizadas, para o casamento lexical."""
    return [t for t in sem_acento(termo).split() if len(t) >= MINIMO_TOKEN]


def escapar_like(texto):
    """Neutraliza os curingas de LIKE (_ casa um caractere qualquer, % casa tudo).

    Nao e preciosismo, e vale para TODO texto do usuario que vira padrao LIKE: o
    prefixo excluido "BKP_" sem escape tiraria tambem BKPA e BKPX, e o token
    "ADM_SSION" daria bonus lexical a ADMISSIONDATE. Escapar a barra primeiro e
    obrigatorio -- fosse depois, ela escaparia o escape que acabamos de por.
    """
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def prefixos(texto):
    """"bkp_, x" -> ["BKP\\_%", "X%"], os padroes LIKE do que sai da busca."""
    padroes = []
    for bruto in (texto or "").split(","):
        prefixo = sem_acento(bruto).strip()
        if prefixo:
            padroes.append(escapar_like(prefixo) + "%")
    return padroes


def lexical(nome, termo):
    """Quanto o nome do objeto/campo casa com o texto digitado, de 0 a 1.

    Nome exato vale tudo. Fora isso vale a fracao dos tokens do termo que
    aparecem no nome -- e o que faz a formula servir tanto para "TDPACIENTE"
    quanto para "cadastro de pacientes internados".
    """
    nome, alvo = sem_acento(nome), sem_acento(termo)
    if alvo and nome == alvo:
        return 1.0
    palavras = tokens(termo)
    if not palavras:
        return 0.0
    casados = sum(1 for t in palavras if t in nome)
    return 0.6 * casados / len(palavras)


def score(cos, nome, termo):
    """A nota que ordena a lista. E dela que a relevancia exibida sai."""
    return PESO_COS * cos + PESO_LEX * lexical(nome, termo)


def relevancia(score_bruto, modelo):
    """score -> 0..100, com o ruido do modelo puxado para o zero.

    Recebe o SCORE, nao o cosseno, de proposito: o numero na tela tem de ser
    monotono com a ordem das linhas. Exibir a relevancia do cosseno enquanto a
    lista ordena por score deixava 45 acima de 60 -- a tela parecia quebrada.

    O zero da escala e o ruido puro: cosseno na linha de base e lexical zerado,
    que da PESO_COS * base. Modelo ainda nao medido cai em base 0 e mostra o
    score cru -- melhor um numero sem calibragem do que um calibrado com a base
    de outro modelo.
    """
    piso = PESO_COS * LINHA_DE_BASE.get(modelo, 0.0)
    return max(0.0, min(100.0, 100 * (score_bruto - piso) / (1 - piso)))


# --------------------------------------------------------------------------
# Consultas
#
# WHERE embedding_modelo = %(modelo)s e OBRIGATORIO em toda consulta com <=>:
# a coluna guarda vetores de modelos diferentes e o operador nao devolve
# resultado ruim quando as dimensoes divergem -- ele levanta erro.
# --------------------------------------------------------------------------

# O lexical em SQL: nome exato, senao a fracao dos tokens presentes no nome.
# Espelha lexical() acima -- mudou um, muda o outro.
LEXICAL = """
    CASE WHEN upper({nome}) = %(termo)s THEN 1.0 ELSE 0.6 * (
        SELECT count(*)::float FROM unnest(%(tokens)s::text[]) t
         WHERE upper({nome}) LIKE '%%' || t || '%%'
    ) / greatest(1, coalesce(array_length(%(tokens)s::text[], 1), 0)) END
"""

# Prefixos que o usuario mandou fora (BKP_, X...). Com a lista vazia o LIKE ANY
# devolve false e o NOT deixa tudo passar -- nao precisa de caso especial.
EXCLUI = "AND NOT (upper({nome}) LIKE ANY (%(excluir)s::text[]))"

# Porte do objeto (registros e colunas) fica FORA do subselect de proposito: o
# LIMIT ja aconteceu la dentro, entao a contagem de colunas roda topk vezes e nao
# uma por objeto vetorizado do catalogo.
SQL_TABELAS = f"""
SELECT r.nome, r.rotulo, r.resumo, r.num_registros,
       (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = r.id) AS n_colunas,
       r.cos, r.score
  FROM (
    SELECT o.id,
           o.nome,
           coalesce(d.rotulo, '') AS rotulo,
           coalesce(d.resumo, '') AS resumo,
           o.num_registros,
           1 - (o.embedding <=> %(vetor)s::vector) AS cos,
           {PESO_COS} * (1 - (o.embedding <=> %(vetor)s::vector))
           + {PESO_LEX} * {LEXICAL.format(nome='o.nome')} AS score
      FROM catalogo.objeto o
      LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
     WHERE o.embedding_modelo = %(modelo)s
       {EXCLUI.format(nome='o.nome')}
     ORDER BY score DESC LIMIT %(topk)s
) r ORDER BY r.score DESC
"""

# O casamento e do campo, mas quem le precisa situar a TABELA dele -- por isso o
# rotulo e o porte do objeto vem junto, e tambem depois do LIMIT.
SQL_CAMPOS = f"""
SELECT r.objeto, r.campo, r.descricao,
       coalesce(d.rotulo, '') AS rotulo,
       o.num_registros,
       (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = o.id) AS n_colunas,
       r.cos, r.score
  FROM (
    SELECT o.id AS objeto_id,
           o.nome AS objeto,
           c.nome AS campo,
           coalesce(c.descricao_ia, '') AS descricao,
           1 - (c.embedding <=> %(vetor)s::vector) AS cos,
           {PESO_COS} * (1 - (c.embedding <=> %(vetor)s::vector))
           + {PESO_LEX} * {LEXICAL.format(nome='c.nome')} AS score
      FROM catalogo.coluna c
      JOIN catalogo.objeto o ON o.id = c.objeto_id
     WHERE c.embedding_modelo = %(modelo)s
       {EXCLUI.format(nome='o.nome')}
     ORDER BY score DESC LIMIT %(topk)s
) r
  JOIN catalogo.objeto o ON o.id = r.objeto_id
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 ORDER BY r.score DESC
"""

# Tabelas no topo, campo que casou como evidencia. O campo promove a tabela dele
# (por isso o greatest), e o LEFT JOIN deixa entrar tabela que so aparece porque
# um campo dela casou -- ela mesma pode nem ter vetor.
SQL_AMBOS = f"""
WITH campo AS (
    SELECT c.objeto_id, c.nome,
           {PESO_COS} * (1 - (c.embedding <=> %(vetor)s::vector))
           + {PESO_LEX} * {LEXICAL.format(nome='c.nome')} AS score,
           1 - (c.embedding <=> %(vetor)s::vector)        AS cos
      FROM catalogo.coluna c
     WHERE c.embedding_modelo = %(modelo)s
),
tabela AS (
    SELECT o.id,
           {PESO_COS} * (1 - (o.embedding <=> %(vetor)s::vector))
           + {PESO_LEX} * {LEXICAL.format(nome='o.nome')} AS score,
           1 - (o.embedding <=> %(vetor)s::vector)        AS cos
      FROM catalogo.objeto o
     WHERE o.embedding_modelo = %(modelo)s
),
melhor AS (
    SELECT objeto_id, max(score) AS score FROM campo GROUP BY objeto_id
),
ranking AS (
SELECT o.id,
       o.nome,
       coalesce(d.rotulo, '') AS rotulo,
       o.num_registros,
       greatest(coalesce(t.score, 0), {PESO_EVIDENCIA} * coalesce(m.score, 0)) AS score,
       coalesce(t.cos, 0) AS cos
  FROM catalogo.objeto o
  LEFT JOIN tabela t ON t.id = o.id
  LEFT JOIN melhor m ON m.objeto_id = o.id
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 WHERE (t.id IS NOT NULL OR m.objeto_id IS NOT NULL)
   {EXCLUI.format(nome='o.nome')}
 ORDER BY score DESC
 LIMIT %(topk)s
)
-- A evidencia vem DEPOIS do LIMIT, e isso vale 2,3 dos 3,8 segundos da busca.
-- Cada volta desta LATERAL varre a CTE `campo` inteira (45 mil linhas) atras dos
-- campos de UM objeto; presa antes do LIMIT ela rodava para os 1.644 candidatos
-- para alimentar 20 linhas de tela. Aqui roda 20 vezes. O `melhor` acima e que
-- ordena o ranking, e ele nao precisa da evidencia -- so do maior score.
SELECT r.nome, r.rotulo, r.num_registros,
       (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = r.id) AS n_colunas,
       r.score, r.cos, ev.campos, ev.campos_score
  FROM ranking r
  LEFT JOIN LATERAL (
      SELECT array_agg(x.nome  ORDER BY x.score DESC) AS campos,
             array_agg(x.score ORDER BY x.score DESC) AS campos_score
        FROM (SELECT nome, score FROM campo
               WHERE objeto_id = r.id ORDER BY score DESC LIMIT {EVIDENCIAS}) x
  ) ev ON true
 ORDER BY r.score DESC
"""

CONSULTA = {"tabelas": SQL_TABELAS, "campos": SQL_CAMPOS, "ambos": SQL_AMBOS}


# --------------------------------------------------------------------------
# Cobertura: em que espaco vetorial da para buscar
# --------------------------------------------------------------------------

SQL_COBERTURA = """
-- O ::int nao e enfeite: sum() devolve numeric e a tela exibiria "230,00".
SELECT modelo,
       sum(objetos)::int AS objetos,
       sum(colunas)::int AS colunas
  FROM (SELECT embedding_modelo AS modelo, count(*) AS objetos, 0 AS colunas
          FROM catalogo.objeto WHERE embedding IS NOT NULL GROUP BY embedding_modelo
         UNION ALL
        SELECT embedding_modelo, 0, count(*)
          FROM catalogo.coluna WHERE embedding IS NOT NULL GROUP BY embedding_modelo) t
 GROUP BY modelo ORDER BY modelo
"""


def cobertura():
    """Quantas tabelas e campos existem em cada modelo. Nao chama API nenhuma."""
    return catalogo.consultar(SQL_COBERTURA, (), "cobertura dos vetores")


# --------------------------------------------------------------------------
# Entrada publica
# --------------------------------------------------------------------------


def buscar(termo, escopo="ambos", topk=20, par=None, excluir=""):
    """Devolve (linhas, meta). UMA chamada paga de embedding por busca.

    Cada linha ja traz `relevancia` (0..100) pronta para a tela; `cos` e `score`
    continuam nela para quem quiser depurar o ranking.
    """
    escopo = escopo if escopo in ESCOPOS else "ambos"
    prov = provedores.escolher(par, capacidade="embedding")

    vetores, _ = embeddings.embutir([termo], prov)
    parametros = {
        "vetor": embeddings.vetor_para_pg(vetores[0]),
        "modelo": prov.modelo,
        "termo": sem_acento(termo),
        # Escapado porque no SQL o token vira padrao LIKE; lexical() aqui do lado
        # compara como substring literal, e os dois tem de dizer a mesma coisa.
        "tokens": [escapar_like(t) for t in tokens(termo)],
        "excluir": prefixos(excluir),
        "topk": topk,
    }

    inicio = time.monotonic()
    linhas = catalogo.consultar(
        CONSULTA[escopo], parametros, f"busca semântica em {escopo}"
    )
    decorrido = time.monotonic() - inicio

    for linha in linhas:
        linha["relevancia"] = round(relevancia(linha["score"], prov.modelo), 1)
        # "NM_PACIENTE (68) · DT_NASC (54)": o campo que puxou a tabela para cima
        if linha.get("campos"):
            linha["evidencia"] = " · ".join(
                f"{nome} ({relevancia(s, prov.modelo):.0f})"
                for nome, s in zip(linha["campos"], linha["campos_score"])
            )

    logger.info(
        "busca '%s' (%s, top %s, exclui %s) via %s: %s resultados em %.0f ms",
        termo, escopo, topk, parametros["excluir"] or "nada",
        prov.modelo, len(linhas), decorrido * 1000,
    )
    meta = {
        "modelo": prov.modelo,
        "provedor": prov.slug,
        "escopo": escopo,
        "resultados": len(linhas),
        "excluidos": len(parametros["excluir"]),
        "ms": round(decorrido * 1000),
    }
    return linhas, meta
