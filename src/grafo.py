"""Vizinhanca de FKs de um objeto, desenhada como SVG no servidor.

Sem biblioteca de grafo: o layout e uma borboleta de tres colunas -- quem aponta
para a tabela a esquerda, a tabela no meio, para quem ela aponta a direita. Isso
acomoda nome comprido (CAPPRESCRIPSCHEDXT) melhor que um layout radial, onde 24
rotulos em volta de um circulo se sobrepoem -- e cresce para baixo, o que deixa
desenhar TODOS os vizinhos sem que um cubra o outro, por mais que sejam.

As cores saem dos tokens do design system: o SVG e inline na pagina, entao
var(--brand) resolve normalmente e o desenho acompanha o tema.
"""

from . import catalogo

SQL_VIZINHOS = """
WITH arestas AS (
  SELECT destino_tabela AS vizinho, 'saindo' AS direcao, origem_colunas AS colunas
    FROM catalogo.relacionamento WHERE origem_tabela = %s
  UNION ALL
  SELECT origem_tabela, 'entrando', origem_colunas
    FROM catalogo.relacionamento WHERE destino_tabela = %s
)
SELECT a.vizinho,
       a.direcao,
       count(*)                                                  AS fks,
       string_agg(DISTINCT array_to_string(a.colunas, ','), ' · ') AS colunas,
       coalesce(o.tem_registros, false)                          AS tem_registros
  FROM arestas a
  LEFT JOIN catalogo.objeto o ON o.nome = a.vizinho
 GROUP BY a.vizinho, a.direcao, o.tem_registros
 ORDER BY count(*) DESC, a.vizinho
"""

# Acima disto o lado perde o rotulo da coluna da FK. Nao e teto de vizinho -- o
# desenho traz todos; e que a 38 arestas convergindo os rotulos viram um borrao
# de "IDADMISSION" repetido em cima do feixe de curvas. A coluna continua legivel
# na lista abaixo do desenho, que tem largura para ela.
TETO_ROTULOS = 12

# Geometria do desenho, em unidades do viewBox
LARGURA_NO = 200
ALTURA_NO = 30
ESPACO_LINHA = 40
VAO = 130  # distancia horizontal entre a coluna lateral e o centro


def vizinhos(nome):
    """Devolve (entrando, saindo) -- cada um ja ordenado por numero de FKs."""
    linhas = catalogo.consultar(SQL_VIZINHOS, (nome, nome), f"vizinhanca de {nome}")
    entrando = [linha for linha in linhas if linha["direcao"] == "entrando"]
    saindo = [linha for linha in linhas if linha["direcao"] == "saindo"]
    return entrando, saindo


def _texto_cortado(valor, limite):
    return valor if len(valor) <= limite else valor[: limite - 1] + "…"


def _no(x, y, rotulo, href=None, centro=False, apagado=False):
    """Retangulo com rotulo; vizinho vira link para a pagina dele."""
    if centro:
        preenchimento, borda, cor = "var(--brand)", "var(--brand)", "var(--brand-on)"
        peso = "600"
    else:
        preenchimento, borda = "var(--surface-card)", "var(--border-default)"
        cor, peso = "var(--text-body)", "400"

    opacidade = ' opacity="0.5"' if apagado else ""
    corpo = (
        f"<g{opacidade}>"
        f'<rect x="{x}" y="{y}" width="{LARGURA_NO}" height="{ALTURA_NO}" rx="6" '
        f'fill="{preenchimento}" stroke="{borda}" stroke-width="1"/>'
        f'<text x="{x + LARGURA_NO / 2}" y="{y + ALTURA_NO / 2 + 4}" text-anchor="middle" '
        f'font-size="12" font-weight="{peso}" fill="{cor}" '
        f'font-family="var(--font-mono)">{_texto_cortado(rotulo, 24)}</text>'
        "</g>"
    )
    return f'<a href="{href}">{corpo}</a>' if href else corpo


def _aresta(x1, y1, x2, y2, cor, marcador, rotulo):
    """Curva de Bezier horizontal + rotulo com a coluna da FK."""
    meio = (x1 + x2) / 2
    caminho = f"M {x1} {y1} C {meio} {y1}, {meio} {y2}, {x2} {y2}"
    curva = (
        f'<path d="{caminho}" fill="none" stroke="{cor}" stroke-width="1.5" '
        f'marker-end="url(#seta-{marcador})" opacity="0.75"/>'
    )
    if not rotulo:
        return curva
    return curva + (
        f'<text x="{meio}" y="{(y1 + y2) / 2 - 5}" text-anchor="middle" font-size="9" '
        f'fill="var(--text-tertiary)" font-family="var(--font-mono)">'
        f"{_texto_cortado(rotulo, 22)}</text>"
    )


def _marcador(id_, cor):
    return (
        f'<marker id="seta-{id_}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" '
        f'markerHeight="5" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{cor}"/></marker>'
    )


COR_ENTRANDO = "var(--brand-controlled)"
COR_SAINDO = "var(--success-text)"


def desenhar(nome, entrando, saindo):
    """SVG da vizinhanca. Devolve None quando a tabela nao tem FK nenhuma."""
    if not entrando and not saindo:
        return None

    # Todos os vizinhos, sem teto. O desenho fica alto -- o maior deste catalogo e
    # GLBENTERPRISE, 39 de um lado, uns 1.600px -- e e o que se quer: a vizinhanca
    # inteira de uma vez, com a pagina rolando. Encolher ESPACO_LINHA para caber nao
    # serve: com o no de 30px de altura, 40 ja e o menor passo que nao sobrepoe um
    # retangulo no outro.
    esq, dir_ = entrando, saindo
    linhas = max(len(esq), len(dir_), 1)

    largura = LARGURA_NO * 3 + VAO * 2
    altura = max(linhas * ESPACO_LINHA + 20, 120)
    meio_y = altura / 2 - ALTURA_NO / 2
    x_esq, x_centro, x_dir = 0, LARGURA_NO + VAO, (LARGURA_NO + VAO) * 2

    def ys(quantos):
        # Coluna centralizada verticalmente em relacao ao no do meio
        topo = altura / 2 - (quantos * ESPACO_LINHA) / 2
        return [topo + i * ESPACO_LINHA for i in range(quantos)]

    partes = [
        f'<svg viewBox="0 0 {largura} {altura}" width="100%" height="{altura}" '
        f'role="img" aria-label="Relacionamentos de {nome}" class="ds-grafo">',
        "<defs>",
        _marcador("entrando", COR_ENTRANDO),
        _marcador("saindo", COR_SAINDO),
        "</defs>",
    ]

    # Arestas primeiro, para os nos ficarem por cima
    for y, viz in zip(ys(len(esq)), esq):
        partes.append(
            _aresta(
                x_esq + LARGURA_NO,
                y + ALTURA_NO / 2,
                x_centro,
                meio_y + ALTURA_NO / 2,
                COR_ENTRANDO,
                "entrando",
                viz["colunas"] if len(esq) <= TETO_ROTULOS else "",
            )
        )
    for y, viz in zip(ys(len(dir_)), dir_):
        partes.append(
            _aresta(
                x_centro + LARGURA_NO,
                meio_y + ALTURA_NO / 2,
                x_dir,
                y + ALTURA_NO / 2,
                COR_SAINDO,
                "saindo",
                viz["colunas"] if len(dir_) <= TETO_ROTULOS else "",
            )
        )

    for y, viz in zip(ys(len(esq)), esq):
        partes.append(
            _no(
                x_esq,
                y,
                viz["vizinho"],
                href=f"/oracle/objetos/{viz['vizinho']}",
                apagado=not viz["tem_registros"],
            )
        )
    for y, viz in zip(ys(len(dir_)), dir_):
        partes.append(
            _no(
                x_dir,
                y,
                viz["vizinho"],
                href=f"/oracle/objetos/{viz['vizinho']}",
                apagado=not viz["tem_registros"],
            )
        )
    partes.append(_no(x_centro, meio_y, nome, centro=True))
    partes.append("</svg>")
    return "".join(partes)


def legenda(entrando, saindo):
    """Frase ao lado do titulo do painel."""
    return " · ".join(
        [
            f"{len(entrando)} apontando para cá",
            f"{len(saindo)} referenciadas por esta",
        ]
    )


# --------------------------------------------------------------------------
# Visao Grafo: o recorte inteiro de uma vez, expandido no cliente
# --------------------------------------------------------------------------

# Sao 209 nos e 424 arestas -- cabe num JSON so, entao o clique expande a partir
# do que ja esta no navegador em vez de bater no servidor a cada no.
# O grafo precisa conter QUALQUER tabela que participe de uma FK, nao so as que
# tem dependentes: os dependentes de uma raiz costumam ser folhas -- apontam para
# ela sem serem apontadas por ninguem. Sem elas aqui, clicar numa raiz nao abriria
# arvore nenhuma, porque a aresta so entra quando as duas pontas estao no conjunto.
ALVO = """
  SELECT o.nome, o.rotulo FROM catalogo.vw_resumo o
   WHERE o.tem_registros
     AND (EXISTS (SELECT 1 FROM catalogo.relacionamento r
                   WHERE r.destino_tabela = o.nome)
       OR EXISTS (SELECT 1 FROM catalogo.relacionamento r
                   WHERE r.origem_tabela = o.nome))
"""

SQL_GRAFO_NOS = f"""
WITH alvo AS ({ALVO})
SELECT a.nome,
       a.rotulo,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.destino_tabela = a.nome)                    AS dependentes,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.origem_tabela = a.nome)                     AS dependencias
  FROM alvo a
 ORDER BY dependentes DESC, a.nome
"""

SQL_GRAFO_ARESTAS = f"""
WITH alvo AS ({ALVO})
SELECT DISTINCT r.origem_tabela AS origem, r.destino_tabela AS destino
  FROM catalogo.relacionamento r
 WHERE r.origem_tabela  IN (SELECT nome FROM alvo)
   AND r.destino_tabela IN (SELECT nome FROM alvo)
"""

# As sementes sao as RAIZES do grafo: tem dependentes mas nenhuma dependencia
# propria. Comecar por elas faz a arvore crescer numa direcao so, em vez de
# abrir no meio do grafo. Raiz nao aponta para ninguem, entao elas nao se ligam
# entre si -- a tela inicial e o conjunto de pontos de entrada do schema.
SQL_SEMENTES = """
SELECT o.nome
  FROM catalogo.objeto o
 WHERE o.tem_registros
   AND EXISTS (SELECT 1 FROM catalogo.relacionamento r WHERE r.destino_tabela = o.nome)
   AND NOT EXISTS (SELECT 1 FROM catalogo.relacionamento r WHERE r.origem_tabela = o.nome)
 ORDER BY (SELECT count(*) FROM catalogo.relacionamento r
            WHERE r.destino_tabela = o.nome) DESC, o.nome
"""


def grafo_completo():
    """Nos e arestas no formato que o cytoscape espera, mais as sementes."""
    nos = catalogo.consultar(SQL_GRAFO_NOS, (), "nós do grafo")
    arestas = catalogo.consultar(SQL_GRAFO_ARESTAS, (), "arestas do grafo")
    sementes = catalogo.consultar(SQL_SEMENTES, (), "raízes do grafo")
    return {
        "nodes": [
            {
                "data": {
                    "id": no["nome"],
                    "rotulo": no["rotulo"] or no["nome"],
                    "nome": no["nome"],
                    "dependentes": no["dependentes"],
                    "dependencias": no["dependencias"],
                }
            }
            for no in nos
        ],
        "edges": [
            {"data": {"source": a["origem"], "target": a["destino"]}} for a in arestas
        ],
        "sementes": [linha["nome"] for linha in sementes],
    }
