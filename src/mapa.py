"""Mapa semantico do schema: as tabelas posicionadas por SIGNIFICADO, nao por FK.

Este modulo e a CONSULTA; src/oracle.py monta a pagina -- a mesma divisao de
src/grafo.py e src/busca.py.

A diferenca para src/grafo.py e o que cada um desenha. O grafo desenha a FK
DECLARADA: a estrutura que o schema diz ter. Aqui a aresta sai do cosseno entre
os vetores de catalogo.objeto -- o que as tabelas dizem SER. As duas visoes
discordando e a informacao: FK entre tabelas sem parentesco nenhum, e parentesco
forte sem FK alguma.

Por que o mapa PARTE DE UMA BUSCA. O kNN aqui e all-pairs, e nao ha como indexar
para acelerar: 4096 dimensoes passa do teto de indice do pgvector (2.000), entao
<=> e sempre varredura exata. O custo e quadratico no tamanho do recorte, e o
catalogo cresceu: com as 230 tabelas vetorizadas do inicio eram 0,69 s; com as
1.649 de hoje sao 72 s -- parede, nao pagina. As 50 tabelas que a busca traz
levam milissegundos, e o recorte ainda por cima e o assunto que se quer ver.

Por isso o recorte entra por `nomes` em mapa(): quem escolhe as tabelas e
busca.buscar(), reaproveitada inteira. Campo continua fora -- sobre os 45 mil
vetorizados nao fecha nem com recorte.
"""

import logging
from collections import defaultdict

from . import busca, catalogo

logger = logging.getLogger(__name__)

# Vizinhos por tabela. Medido neste catalogo, o cosseno do k-esimo vizinho cai de
# 0,906 (mediana do 1o) para 0,786 (mediana do 6o) -- ainda muito acima do ruido.
# Passar disso comeca a ligar tabela com tabela por acaso e o mapa vira bola.
K = 6

# Piso do cosseno para a aresta existir. O numero que importa aqui e o RUIDO:
# dois vetores sem relacao nenhuma ja pontuam 0,456 neste modelo
# (busca.LINHA_DE_BASE, medido sobre 300 pares ao acaso). 0,70 fica bem acima
# dele sem cortar vizinhanca legitima.
PISO = 0.70

# Acima disto as duas tabelas sao a mesma coisa dita duas vezes. Nos 230
# vetorizados sao 60 pares, e os campeoes sao exatamente as copias de snapshot:
# XCAPCONSULT_20240206_2 x XYXXCAPCONSULT_20201215_S da 0,9853.
GEMEA = 0.95

# Teto de passos do label propagation. Em 230 nos ele estabiliza em menos de 10;
# o teto so garante que a funcao termina se ficar oscilando entre dois rotulos.
PASSOS = 20


# --------------------------------------------------------------------------
# Consultas
#
# WHERE embedding_modelo = %(modelo)s e OBRIGATORIO em toda consulta com <=>:
# a coluna guarda vetores de modelos diferentes e o operador nao devolve
# resultado ruim quando as dimensoes divergem -- ele levanta erro.
# --------------------------------------------------------------------------

# O recorte, repetido nas tres consultas: tabela com vetor no modelo pedido, menos
# os prefixos que o usuario mandou fora. Com a lista vazia o LIKE ANY devolve
# false e o NOT deixa tudo passar -- nao precisa de caso especial.
RECORTE = """
       o.embedding_modelo = %(modelo)s
   AND NOT (upper(o.nome) LIKE ANY (%(excluir)s::text[]))
   AND (%(nomes)s::text[] IS NULL OR o.nome = ANY(%(nomes)s::text[]))
"""

# ORDER BY o.nome nao e enfeite: a posicao na lista vira o INDICE do ponto no
# cosmos, e as arestas referenciam indice, nao nome. Ordem instavel trocaria as
# arestas de lugar a cada request.
SQL_NOS = f"""
SELECT o.nome,
       coalesce(d.rotulo, o.nome) AS rotulo,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.destino_tabela = o.nome) AS dependentes,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.origem_tabela = o.nome)  AS dependencias
  FROM catalogo.objeto o
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 WHERE {RECORTE}
 ORDER BY o.nome
"""

# O LATERAL e o kNN: para cada tabela, as K mais proximas. Ordenar pela distancia
# (<=>) e nao pelo cosseno deixa o plano usar a mesma expressao do ORDER BY.
SQL_VIZINHOS = f"""
WITH v AS (
  SELECT o.id, o.nome, o.embedding
    FROM catalogo.objeto o
   WHERE {RECORTE}
)
SELECT a.nome AS origem, k.nome AS destino, k.cos
  FROM v a
  CROSS JOIN LATERAL (
    SELECT b.nome, 1 - (a.embedding <=> b.embedding) AS cos
      FROM v b
     WHERE b.id <> a.id
     ORDER BY a.embedding <=> b.embedding
     LIMIT %(k)s
  ) k
 WHERE k.cos >= %(piso)s
"""

# Auto-FK fica de fora (sao 14 no recorte): o cosmos nao desenha laco, e a aresta
# de um no para ele mesmo nao diz nada sobre parentesco entre tabelas.
SQL_FKS = f"""
WITH v AS (
  SELECT o.nome FROM catalogo.objeto o WHERE {RECORTE}
)
SELECT DISTINCT r.origem_tabela AS origem, r.destino_tabela AS destino
  FROM catalogo.relacionamento r
 WHERE r.origem_tabela  IN (SELECT nome FROM v)
   AND r.destino_tabela IN (SELECT nome FROM v)
   AND r.origem_tabela <> r.destino_tabela
"""


# --------------------------------------------------------------------------
# Montagem do grafo (puro -- e o que os testes cobrem)
# --------------------------------------------------------------------------


def par(a, b):
    """Chave canonica de uma aresta nao-dirigida.

    O kNN e dirigido: A pode ter B entre os seus 6 sem que B tenha A. As duas
    metades sao a MESMA aresta, e sem esta normalizacao o mapa desenharia duas
    linhas sobrepostas com a mesma espessura, dobrando o peso visual do par.
    """
    return (a, b) if a <= b else (b, a)


def arestas(vizinhos, fks):
    """Junta kNN e FK num conjunto so de arestas nao-dirigidas classificadas.

    Os quatro tipos, e o que cada um responde na tela:

      gemea  cosseno >= GEMEA -- o mesmo conceito modelado duas vezes
      ambos  FK declarada E vizinhanca semantica -- o modelo confere
      fk     FK declarada SEM vizinhanca -- a ligacao existe no schema e nao no
             significado (CAPEQUIPMRENTALMAT -> CAPFINANCIALDOC da 0,514, ruido)
      sim    vizinhanca sem FK -- parentesco que o schema nao declara

    Devolve a lista ordenada, para o JSON sair igual a cada request.
    """
    cos_do_par = {}
    for linha in vizinhos:
        chave = par(linha["origem"], linha["destino"])
        # Duas metades do mesmo par podem trazer o mesmo cosseno; max() e por
        # seguranca numerica, nao porque os valores devessem divergir.
        cos_do_par[chave] = max(cos_do_par.get(chave, 0.0), float(linha["cos"]))

    pares_fk = {par(linha["origem"], linha["destino"]) for linha in fks}

    saida = []
    for chave in sorted(cos_do_par.keys() | pares_fk):
        cos = cos_do_par.get(chave)
        tem_fk = chave in pares_fk
        if cos is not None and cos >= GEMEA:
            tipo = "gemea"
        elif tem_fk and cos is not None:
            tipo = "ambos"
        elif tem_fk:
            tipo = "fk"
        else:
            tipo = "sim"
        saida.append({
            "origem": chave[0],
            "destino": chave[1],
            "tipo": tipo,
            # FK sem vizinhanca nao tem cosseno calculado: o kNN so devolveu os K
            # mais proximos, e este par ficou de fora justamente por ser distante.
            "cos": round(cos, 4) if cos is not None else None,
        })
    return saida


def comunidades(nomes, ligacoes):
    """Label propagation sobre as arestas semanticas. Devolve {nome: id do tema}.

    Cada no adota o rotulo mais frequente entre os vizinhos, e repete ate ninguem
    mudar. Sao os blocos de assunto do schema -- clinico, faturamento, cadastro --
    sem que ninguem os tenha nomeado.

    Determinismo importa: a cor do tema nao pode trocar a cada F5. Por isso os
    nos sao varridos em ordem alfabetica e o empate cai sempre no menor rotulo,
    em vez do sorteio que a formulacao classica usa.
    """
    vizinhanca = defaultdict(set)
    for ligacao in ligacoes:
        # So a semantica agrupa. Incluir a aresta "fk" aqui misturaria no mesmo
        # tema justamente os pares que a tela existe para mostrar SEPARADOS.
        if ligacao["tipo"] == "fk":
            continue
        vizinhanca[ligacao["origem"]].add(ligacao["destino"])
        vizinhanca[ligacao["destino"]].add(ligacao["origem"])

    ordem = sorted(nomes)
    rotulo = {nome: i for i, nome in enumerate(ordem)}

    for _ in range(PASSOS):
        mudou = False
        for nome in ordem:
            vizinhos = vizinhanca.get(nome)
            if not vizinhos:
                continue
            contagem = defaultdict(int)
            for vizinho in vizinhos:
                contagem[rotulo[vizinho]] += 1
            # max() pelo par (frequencia, -rotulo): mais frequente vence, e o
            # empate fica com o menor rotulo em vez de depender da ordem do dict.
            melhor = max(contagem.items(), key=lambda item: (item[1], -item[0]))[0]
            if melhor != rotulo[nome]:
                rotulo[nome] = melhor
                mudou = True
        if not mudou:
            break

    # Os rotulos sobreviventes sao ids esparsos (0, 7, 43...). Reindexar para
    # 0..n-1 deixa o JS usar o id direto como posicao na paleta.
    temas = sorted({rotulo[nome] for nome in ordem})
    indice = {tema: i for i, tema in enumerate(temas)}
    return {nome: indice[rotulo[nome]] for nome in ordem}


def nomear_temas(nos, tema):
    """Um nome para cada bloco, escrito sobre ele na tela.

    Sem isto o tema so existiria como cor, e sao 16 blocos -- muito acima do que
    uma escala categorica aguenta distinguir. Quem separa os temas na tela e a
    POSICAO (a forca de cluster do cosmos), e o nome e o que os identifica; a cor
    fica livre para as arestas, que carregam as outras duas perguntas da pagina.

    O nome sai da tabela mais central do bloco -- a com mais dependentes, que e a
    que as outras referenciam. Empate cai no nome alfabetico, para o rotulo nao
    dancar entre dois candidatos a cada request.
    """
    membros = defaultdict(list)
    for no in nos:
        membros[tema[no["nome"]]].append(no)

    saida = []
    for id_tema, grupo in sorted(membros.items()):
        principal = max(grupo, key=lambda no: (no["dependentes"], no["dependencias"]))
        empatados = [
            no for no in grupo
            if (no["dependentes"], no["dependencias"])
            == (principal["dependentes"], principal["dependencias"])
        ]
        principal = min(empatados, key=lambda no: no["nome"])
        saida.append({
            "id": id_tema,
            "nome": principal["rotulo"],
            "tabela": principal["nome"],
            "tamanho": len(grupo),
        })
    return saida


# --------------------------------------------------------------------------
# Entrada publica
# --------------------------------------------------------------------------


def mapa(modelo, excluir="", nomes=None):
    """Nos, arestas e duplicatas do recorte. Nao chama API nenhuma.

    `nomes` restringe o mapa a um conjunto de tabelas -- e por onde entra o
    resultado da busca semantica. Com None desenha o recorte inteiro, como sempre
    fez. O filtro vive dentro do RECORTE, que as tres consultas compartilham:
    assim no, vizinhanca e FK enxergam o mesmo universo. Restringir so os nos
    deixaria aresta apontando para tabela que nao esta no desenho.

    Aqui nao ha embedding a gerar: os vetores ja estao no banco. Quem paga a
    chamada e a busca, ANTES de chegar aqui -- ver oracle.dados_do_mapa.
    """
    parametros = {
        # prefixos() ja escapa _ e % -- sem isso o prefixo "BKP_" excluiria
        # tambem BKPA e companhia, porque em LIKE o _ e curinga.
        "excluir": busca.prefixos(excluir),
        "nomes": list(nomes) if nomes is not None else None,
        "modelo": modelo,
        "k": K,
        "piso": PISO,
    }
    nos = catalogo.consultar(SQL_NOS, parametros, "nós do mapa semântico")
    vizinhos = catalogo.consultar(SQL_VIZINHOS, parametros, "vizinhança semântica")
    fks = catalogo.consultar(SQL_FKS, parametros, "FKs do mapa semântico")

    ligacoes = arestas(vizinhos, fks)
    nomes = [no["nome"] for no in nos]
    tema = comunidades(nomes, ligacoes)

    gemeas = [
        {"a": l["origem"], "b": l["destino"], "cos": l["cos"]}
        for l in sorted(ligacoes, key=lambda l: -(l["cos"] or 0))
        if l["tipo"] == "gemea"
    ]
    temas = nomear_temas(nos, tema)

    logger.info(
        "mapa semantico (%s, excluindo %s, recorte %s): %s nos, %s arestas, "
        "%s temas, %s gemeas",
        modelo, parametros["excluir"] or "nada",
        f"{len(nomes)} tabelas da busca" if nomes is not None else "schema inteiro",
        len(nos), len(ligacoes), len(set(tema.values())), len(gemeas),
    )
    return {
        "nodes": [
            {
                "nome": no["nome"],
                "rotulo": no["rotulo"],
                "tema": tema[no["nome"]],
                "dependentes": no["dependentes"],
                "dependencias": no["dependencias"],
            }
            for no in nos
        ],
        "edges": ligacoes,
        "temas": temas,
        "gemeas": gemeas,
        "meta": {
            "modelo": modelo,
            "nos": len(nos),
            "arestas": len(ligacoes),
            "temas": len(set(tema.values())),
            "k": K,
            "piso": PISO,
            "gemea": GEMEA,
        },
    }
