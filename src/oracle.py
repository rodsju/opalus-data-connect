"""Conteudo das rotas /oracle: catalogo do schema Oracle extraido para o Postgres.

As sete listagens sao a mesma pagina com outra consulta, entao vivem num dicionario
de configuracao em vez de sete modulos. Quem le o banco e src/catalogo.py; o HTML
fica em src/templates/oracle.html e oracle_lista.html.
"""

import json
from urllib.parse import quote_plus

from . import busca, catalogo, embeddings, grafo, ia, layout, mapa, provedores

VOLTAR = "/oracle"

# "Tem registros" vem da amostra, nao da estatistica do Oracle: em 3 tabelas de log
# o ALL_TABLES.num_rows era de marco/2026 e ja nao valia -- a amostra veio vazia.
# Por isso o recorte olha tem_registros, que a extracao sempre preenche.
COM_REGISTROS = "SELECT nome FROM catalogo.objeto WHERE tem_registros"
# "Dependente" e quem aponta para ca: a chave desta tabela e usada como FK por outra.
COM_DEPENDENTES = "SELECT DISTINCT destino_tabela FROM catalogo.relacionamento"
COM_DEPENDENCIAS = "SELECT DISTINCT origem_tabela FROM catalogo.relacionamento"

# Os tres tipos de controle da barra. `flag` e o checkbox de sempre; os outros
# dois existem porque campo de tres estados e filtro por valor nao cabem num
# checkbox -- "sempre nulo" tem sim, nao e nao-avaliada, e nao adianta oferecer
# so um deles.
#
# (chave interna, nome na querystring, rotulo, tipo). O nome na URL difere da
# chave em "registros" porque com_registros ja estava publicado antes dos outros.
FILTROS = (
    ("registros", "com_registros", "Só com registros", "flag"),
    ("dependentes", "dependentes", "Só com dependentes", "flag"),
    ("dependencias", "dependencias", "Só com dependências", "flag"),
    ("sensivel", "sensivel", "Sensível", "estado"),
    ("categoria", "categoria", "Categoria", "escolha"),
    ("sempre_nulo", "sempre_nulo", "Sempre nulo", "estado"),
)
PARAM_DO_FILTRO = {chave: param for chave, param, _, _ in FILTROS}
TIPO_DO_FILTRO = {chave: tipo for chave, _, _, tipo in FILTROS}

# Valores do filtro de estado -> como testar a expressao que a secao declarou.
#
# `IS FALSE`, e nao `NOT <expr>`: em SQL `NOT NULL` e NULL, entao o NOT deixaria
# a linha nao avaliada fora dos dois lados sem ninguem perceber. A diferenca
# entre "tem valor" e "nao sei" e justamente o que esta barra existe para separar.
ESTADOS = {
    "sim": "{expr}",
    "nao": "{expr} IS FALSE",
    "nao_avaliada": "{expr} IS NULL",
}
ROTULO_DO_ESTADO = (
    ("", "qualquer"),
    ("sim", "sim"),
    ("nao", "não"),
    ("nao_avaliada", "não avaliada"),
)

# As opcoes do filtro de escolha, por chave. A lista de categorias sai de ia.py,
# que e quem define o dominio e valida a resposta do modelo -- duplicar aqui e
# garantir que as duas divirjam.
OPCOES = {"categoria": ia.CATEGORIAS}


def montar_recorte(disponiveis, valores):
    """Filtros escolhidos -> (predicado SQL, parametros).

    `disponiveis` e o que a secao declara: para `flag`, o predicado pronto; para
    `estado` e `escolha`, a EXPRESSAO a testar. Valor que a secao nao oferece, ou
    que nao esta na lista de opcoes, e ignorado -- a barra so mostra o que vale,
    mas a URL pode vir digitada a mao.
    """
    predicados, params = [], []
    for chave, _, _, tipo in FILTROS:
        if chave not in disponiveis:
            continue
        valor = valores.get(chave)
        if not valor:
            continue
        expressao = disponiveis[chave]
        if tipo == "flag":
            predicados.append(expressao)
        elif tipo == "estado" and valor in ESTADOS:
            predicados.append(ESTADOS[valor].format(expr=expressao))
        elif tipo == "escolha" and valor in OPCOES.get(chave, ()):
            # Parametro, nunca interpolado: o valor vem do usuario.
            predicados.append(f"{expressao} = %s")
            params.append(valor)
    return (" AND ".join(predicados) or None), tuple(params)

# Cada secao: de onde ler, o que mostrar e por onde buscar. `campos` e a ordem das
# colunas na tela -- (chave devolvida pelo SELECT, rotulo, alinha a direita).
SECOES = {
    "objetos": {
        "titulo": "Objetos",
        "descricao": "Tabelas e views do schema, com o panorama de cada uma.",
        "origem": "catalogo.vw_resumo",
        "colunas": (
            "nome, rotulo, tipo, num_registros, tem_registros, n_colunas, tem_pk, "
            "fks_saindo, fks_entrando, linhas_amostra"
        ),
        "campos": [
            ("nome", "Objeto", False),
            ("rotulo", "Rótulo (IA)", False),
            ("tipo", "Tipo", False),
            ("num_registros", "Registros", True),
            ("tem_registros", "Com registros", False),
            ("n_colunas", "Colunas", True),
            ("tem_pk", "PK", False),
            ("fks_saindo", "FK saindo", True),
            ("fks_entrando", "FK entrando", True),
            ("linhas_amostra", "Amostra", True),
        ],
        "busca": ["nome"],
        "ordem": "nome",
        "filtros": {
            "registros": "tem_registros",
            "dependentes": f"nome IN ({COM_DEPENDENTES})",
            "dependencias": f"nome IN ({COM_DEPENDENCIAS})",
        },
        "link": ("nome", "/oracle/objetos/{}"),
    },
    "dicionario": {
        "titulo": "Dicionário",
        "descricao": "Todas as colunas do schema, com tipo, nulidade e comentário.",
        "origem": "catalogo.vw_dicionario",
        "colunas": (
            "objeto, posicao, coluna, tipo_completo, aceita_nulo, eh_pk, "
            "valor_default, comentario, descricao_ia, sensivel_categoria, sempre_nulo"
        ),
        "campos": [
            ("objeto", "Objeto", False),
            ("posicao", "#", True),
            ("coluna", "Coluna", False),
            ("tipo_completo", "Tipo", False),
            ("aceita_nulo", "Aceita nulo", False),
            ("eh_pk", "PK", False),
            ("valor_default", "Default", False),
            ("comentario", "Comentário", False),
            ("descricao_ia", "Descrição (IA)", False),
            ("sensivel_categoria", "Sensível (IA)", False),
            ("sempre_nulo", "Sempre nulo", False),
        ],
        "busca": ["objeto", "coluna"],
        "ordem": "objeto, posicao",
        "link": ("objeto", "/oracle/objetos/{}"),
        # `flag` declara o predicado pronto; `estado` e `escolha` declaram a
        # EXPRESSAO a testar -- quem monta o predicado e montar_recorte().
        "filtros": {
            "sensivel": "sensivel",
            "categoria": "sensivel_categoria",
            "sempre_nulo": "sempre_nulo",
            "registros": f"objeto IN ({COM_REGISTROS})",
            "dependentes": f"objeto IN ({COM_DEPENDENTES})",
            "dependencias": f"objeto IN ({COM_DEPENDENCIAS})",
        },
    },
    "relacionamentos": {
        "titulo": "Relacionamentos",
        "descricao": "As chaves estrangeiras declaradas, aresta a aresta.",
        "origem": "catalogo.vw_relacionamentos",
        "colunas": "origem, destino, constraint_nome, delete_rule",
        "campos": [
            ("origem", "Origem", False),
            ("destino", "Destino", False),
            ("constraint_nome", "Constraint", False),
            ("delete_rule", "Delete rule", False),
        ],
        # Busca em `origem`/`destino`, que sao TABELA.COLUNA -- as MESMAS colunas
        # que a tela mostra. Buscava em origem_tabela/destino_tabela, so o nome da
        # tabela, entao "IDADMISSION" nao achava nada apesar de aparecer em 37
        # linhas na tela. O nome da tabela continua achando: ele e o prefixo.
        "busca": ["origem", "destino"],
        "ordem": "origem_tabela, constraint_nome",
        "filtros": {"registros": f"origem_tabela IN ({COM_REGISTROS})"},
    },
    "orfas": {
        "titulo": "Órfãs",
        "descricao": (
            "Tabelas sem FK entrando nem saindo — quase sempre "
            "relacionamento não declarado."
        ),
        "origem": "catalogo.vw_orfas",
        "colunas": "nome, tipo, num_registros, n_colunas",
        "campos": [
            ("nome", "Objeto", False),
            ("tipo", "Tipo", False),
            ("num_registros", "Registros", True),
            ("n_colunas", "Colunas", True),
        ],
        "busca": ["nome"],
        "ordem": "nome",
        "filtros": {"registros": f"nome IN ({COM_REGISTROS})"},
        "link": ("nome", "/oracle/objetos/{}"),
    },
    "amostras": {
        "titulo": "Amostras",
        "descricao": (
            "Linhas coletadas de cada objeto, como estão na origem. A extração "
            "pega os registros mais recentes quando a tabela deixa ordenar barato."
        ),
        "origem": "catalogo.amostra a JOIN catalogo.objeto o ON o.id = a.objeto_id",
        "colunas": "o.nome AS objeto, a.linha, a.mascarada, a.dados",
        "campos": [
            ("objeto", "Objeto", False),
            ("linha", "Linha", True),
            ("mascarada", "Mascarada", False),
            ("dados", "Dados", False),
        ],
        "busca": ["o.nome"],
        "ordem": "o.nome, a.linha",
        "link": ("objeto", "/oracle/objetos/{}"),
        "filtros": {},
    },
    "indices": {
        "titulo": "Índices",
        "descricao": "Índices por objeto, com as colunas que cobrem.",
        "origem": "catalogo.indice i JOIN catalogo.objeto o ON o.id = i.objeto_id",
        "colunas": "o.nome AS objeto, i.nome, i.unico, i.tipo, i.colunas",
        "campos": [
            ("objeto", "Objeto", False),
            ("nome", "Índice", False),
            ("unico", "Único", False),
            ("tipo", "Tipo", False),
            ("colunas", "Colunas", False),
        ],
        "busca": ["o.nome", "i.nome"],
        "ordem": "o.nome, i.nome",
        "link": ("objeto", "/oracle/objetos/{}"),
        "filtros": {"registros": "o.tem_registros"},
    },
    "restricoes": {
        "titulo": "Restrições",
        "descricao": (
            "Primárias (P), únicas (U) e estrangeiras (R) — o extrator "
            "não traz check constraints."
        ),
        "origem": "catalogo.restricao r JOIN catalogo.objeto o ON o.id = r.objeto_id",
        "colunas": (
            "o.nome AS objeto, r.nome, r.tipo, r.colunas, "
            "r.ref_tabela, r.ref_colunas, r.delete_rule"
        ),
        "campos": [
            ("objeto", "Objeto", False),
            ("nome", "Restrição", False),
            ("tipo", "Tipo", False),
            ("colunas", "Colunas", False),
            ("ref_tabela", "Referencia", False),
            ("ref_colunas", "Colunas ref.", False),
            ("delete_rule", "Delete rule", False),
        ],
        "busca": ["o.nome", "r.nome"],
        "ordem": "o.nome, r.nome",
        "link": ("objeto", "/oracle/objetos/{}"),
        "filtros": {"registros": "o.tem_registros"},
    },
}


def texto(valor):
    """Achata o que o Postgres devolve e a macro tabela() nao saberia exibir."""
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, list):
        return ", ".join(str(item) for item in valor)
    if isinstance(valor, dict):
        return json.dumps(valor, ensure_ascii=False, default=str)
    return valor


def montar_tabela(campos, linhas, link=None):
    """Colunas e celulas no formato que a macro tabela() de macros.html espera.

    `link` e (chave, molde) -- a celula daquela chave vira <a>, com o molde
    recebendo o valor cru. Ex.: ("nome", "/oracle/objetos/{}").
    """
    colunas = [{"rotulo": rotulo, "num": num} for _, rotulo, num in campos]
    chave_link, molde = link if link else (None, None)
    celulas = []
    for linha in linhas:
        celula_linha = []
        for chave, _, num in campos:
            celula = {"valor": texto(linha[chave]), "num": num}
            if chave == chave_link and linha[chave]:
                celula["href"] = molde.format(linha[chave])
            celula_linha.append(celula)
        celulas.append(celula_linha)
    return colunas, celulas


def pagina_erro(falha, usuario, caminho):
    html = layout.render(
        "erro.html",
        "Não conseguimos ler o catálogo",
        usuario,
        caminho,
        crumb="Oracle",
        descricao="O catálogo fica no Postgres, alimentado por scripts/mapear_oracle.py.",
        alvo=falha.descricao,
        detalhe=str(falha.causa),
        voltar=caminho,
    )
    return html, 502


# --------------------------------------------------------------------------
# Listagens
# --------------------------------------------------------------------------


def gerar_lista(secao, pagina, por_pagina, termo, valores=None, usuario=None):
    """Devolve (html, status_code) para uma das secoes de SECOES.

    `valores` e {chave do filtro: valor escolhido}. Filtro que a secao nao
    declara, ou valor que nao esta na lista, e ignorado em vez de dar erro -- a
    barra so oferece o que vale, mas a URL pode vir digitada a mao.
    """
    config = SECOES[secao]
    caminho = f"/oracle/{secao}"
    termo = (termo or "").strip()

    disponiveis = config["filtros"]
    valores = {c: v for c, v in (valores or {}).items() if c in disponiveis and v}
    recorte, params_recorte = montar_recorte(disponiveis, valores)

    try:
        linhas, pag = catalogo.listar(
            config["colunas"],
            config["origem"],
            config["busca"],
            termo,
            pagina,
            por_pagina,
            config["ordem"],
            recorte,
            params_recorte,
        )
    except catalogo.ConsultaFalhou as falha:
        return pagina_erro(falha, usuario, caminho)

    # A paginacao remonta a URL a cada link, entao os filtros precisam sobreviver nela
    partes = [f"q={quote_plus(termo)}"] if termo else []
    partes += [
        f"{PARAM_DO_FILTRO[chave]}={quote_plus(valor)}"
        for chave, valor in valores.items()
    ]
    pag["base"] = caminho + "?" + ("&".join(partes) + "&" if partes else "")

    colunas, celulas = montar_tabela(config["campos"], linhas, config.get("link"))
    html = layout.render(
        "oracle_lista.html",
        config["titulo"],
        usuario,
        caminho,
        crumb="Oracle",
        descricao=config["descricao"],
        colunas=colunas,
        linhas=celulas,
        pag=pag,
        termo=termo,
        filtros=[
            {
                "param": param,
                "rotulo": rotulo,
                "tipo": tipo,
                "valor": valores.get(chave, ""),
                "opcoes": (
                    ROTULO_DO_ESTADO
                    if tipo == "estado"
                    else [("", "qualquer")] + [(o, o) for o in OPCOES.get(chave, ())]
                ),
            }
            for chave, param, rotulo, tipo in FILTROS
            if chave in disponiveis
        ],
        faixa=layout.faixa_exibida(pag, linhas),
        acao=caminho,
    )
    return html, 200


# --------------------------------------------------------------------------
# Visao geral
# --------------------------------------------------------------------------

SQL_CONTAGENS = """
SELECT (SELECT count(*) FROM catalogo.objeto)                        AS objetos,
       (SELECT count(*) FROM catalogo.objeto WHERE tipo = 'TABLE')   AS tabelas,
       (SELECT count(*) FROM catalogo.objeto WHERE tipo = 'VIEW')    AS views,
       (SELECT count(*) FROM catalogo.objeto WHERE tem_registros)    AS com_registros,
       (SELECT count(*) FROM catalogo.objeto
         WHERE NOT tem_registros AND num_registros = 0)              AS vazias_zeradas,
       (SELECT count(*) FROM catalogo.objeto
         WHERE NOT tem_registros AND num_registros IS NULL)          AS vazias_sem_stat,
       (SELECT count(*) FROM catalogo.objeto
         WHERE NOT tem_registros AND num_registros > 0)              AS vazias_stat_velha,
       (SELECT count(*) FROM catalogo.coluna)                        AS colunas,
       (SELECT count(*) FROM catalogo.coluna c
          JOIN catalogo.objeto o ON o.id = c.objeto_id
         WHERE o.tem_registros)                                      AS colunas_com_registros,
       (SELECT count(*) FROM catalogo.restricao)                     AS restricoes,
       (SELECT count(*) FROM catalogo.indice)                        AS indices,
       (SELECT count(*) FROM catalogo.relacionamento)                AS relacionamentos,
       (SELECT count(*) FROM catalogo.amostra)                       AS amostras,
       (SELECT count(*) FROM catalogo.vw_orfas)                      AS orfas,
       (SELECT count(*) FROM catalogo.vw_orfas v
          JOIN catalogo.objeto o ON o.nome = v.nome
         WHERE o.tem_registros)                                      AS orfas_com_registros
"""

SQL_CLASSES = """
WITH c AS (
  SELECT o.nome,
         EXISTS (SELECT 1 FROM catalogo.relacionamento r
                  WHERE r.destino_tabela = o.nome) AS tem_dependentes,
         EXISTS (SELECT 1 FROM catalogo.relacionamento r
                  WHERE r.origem_tabela = o.nome)  AS tem_dependencias
    FROM catalogo.objeto o
   WHERE o.tem_registros
)
SELECT count(*) FILTER (WHERE tem_dependentes)                        AS dependentes,
       count(*) FILTER (WHERE tem_dependencias)                       AS dependencias,
       count(*) FILTER (WHERE tem_dependentes AND tem_dependencias)   AS ambos,
       count(*) FILTER (WHERE NOT tem_dependentes
                          AND NOT tem_dependencias)                   AS isoladas,
       count(*)                                                       AS total
  FROM c
"""

SQL_MAIORES = """
SELECT nome, num_registros, n_colunas, fks_saindo, fks_entrando
  FROM catalogo.vw_resumo
 WHERE num_registros IS NOT NULL
 ORDER BY num_registros DESC
 LIMIT 10
"""

def montar_classes(classes):
    """Uma linha por recorte, cada uma linkando para a listagem que a produz.

    As duas primeiras se sobrepoem (uma tabela pode ter dependente E dependencia),
    por isso "ambos" aparece explicito em vez de fingir que a soma fecha.
    """
    base = "/oracle/objetos?com_registros=1"
    return [
        (
            "Têm dependentes",
            "a chave delas é usada como FK por outra tabela",
            classes["dependentes"],
            f"{base}&dependentes=1",
        ),
        (
            "Têm dependências",
            "usam a chave de outra tabela",
            classes["dependencias"],
            f"{base}&dependencias=1",
        ),
        (
            "Têm ambos",
            "estão no meio do grafo — a sobreposição das duas linhas acima",
            classes["ambos"],
            f"{base}&dependentes=1&dependencias=1",
        ),
        (
            "Sem relacionamento declarado",
            "nenhuma FK entrando nem saindo, apesar de terem dados",
            classes["isoladas"],
            "/oracle/orfas?com_registros=1",
        ),
    ]


CAMPOS_MAIORES = [
    ("nome", "Objeto", False),
    ("num_registros", "Registros", True),
    ("n_colunas", "Colunas", True),
    ("fks_saindo", "FK saindo", True),
    ("fks_entrando", "FK entrando", True),
]


def montar_kpis(contagens):
    objetos = contagens["objetos"]
    com = contagens["com_registros"]
    vazias = objetos - com
    orfas = contagens["orfas"]

    def parcela(quantidade):
        return f"{quantidade * 100 // objetos}% do schema" if objetos else ""

    # As "vazias" com estatistica > 0 sao stat velha do Oracle, nao contradicao
    detalhe_vazias = [f"{layout.fmt(contagens['vazias_zeradas'])} zeradas"]
    if contagens["vazias_sem_stat"]:
        detalhe_vazias.append(f"{layout.fmt(contagens['vazias_sem_stat'])} sem estatística")
    if contagens["vazias_stat_velha"]:
        detalhe_vazias.append(
            f"{layout.fmt(contagens['vazias_stat_velha'])} com estatística vencida"
        )

    return [
        {
            "rotulo": "Objetos",
            "valor": layout.fmt(objetos),
            "hint": f"{layout.fmt(contagens['tabelas'])} tabelas · "
            f"{layout.fmt(contagens['views'])} views",
        },
        {"rotulo": "Com registros", "valor": layout.fmt(com), "hint": parcela(com)},
        {
            "rotulo": "Sem registros",
            "valor": layout.fmt(vazias),
            "hint": " · ".join(detalhe_vazias),
        },
        {
            "rotulo": "Colunas",
            "valor": layout.fmt(contagens["colunas"]),
            "hint": f"{layout.fmt(contagens['colunas_com_registros'])} "
            "em tabelas com registros",
        },
        {
            "rotulo": "Relacionamentos",
            "valor": layout.fmt(contagens["relacionamentos"]),
            "hint": f"{layout.fmt(contagens['restricoes'])} restrições · "
            f"{layout.fmt(contagens['indices'])} índices",
        },
        {
            "rotulo": "Tabelas órfãs",
            "valor": layout.fmt(orfas),
            "hint": f"{layout.fmt(contagens['orfas_com_registros'])} com registros",
        },
    ]


def montar_extracao(extracao):
    """Pares rotulo/valor da ultima extracao, para a macro tabela_itens()."""
    if not extracao:
        return [], []
    itens = [
        ("Schema de origem", extracao["schema_origem"]),
        ("Host", extracao["host"]),
        ("Service name", extracao["service_name"]),
        ("Situação", extracao["status"]),
        ("Iniciada em", layout.fmt(extracao["iniciada_em"])),
        ("Concluída em", layout.fmt(extracao["concluida_em"])),
    ]
    for chave, valor in sorted(extracao["parametros"].items()):
        itens.append((f"Parâmetro · {chave}", texto(valor) if valor is not None else "—"))
    return itens, extracao["erros"]


def gerar_visao_geral(usuario=None):
    try:
        extracao = catalogo.um(
            "SELECT * FROM catalogo.extracao WHERE id = 1", (), "estado da extração"
        )
        contagens = catalogo.um(SQL_CONTAGENS, (), "contagens do catálogo")
        classes = catalogo.um(SQL_CLASSES, (), "classificação por relacionamento")
        maiores = catalogo.consultar(SQL_MAIORES, (), "maiores objetos")
    except catalogo.ConsultaFalhou as falha:
        return pagina_erro(falha, usuario, VOLTAR)

    itens, erros = montar_extracao(extracao)
    colunas, celulas = montar_tabela(CAMPOS_MAIORES, maiores)
    html = layout.render(
        "oracle.html",
        "Catálogo Oracle",
        usuario,
        VOLTAR,
        crumb="Oracle",
        descricao="Foto do schema extraída para o Postgres por scripts/mapear_oracle.py.",
        cards=montar_kpis(contagens),
        classes=montar_classes(classes),
        classes_total=classes["total"],
        extracao=extracao,
        itens=itens,
        erros=erros,
        colunas=colunas,
        linhas=celulas,
    )
    return html, 200


# --------------------------------------------------------------------------
# Detalhe de um objeto: vizinhanca de FKs + descricao gerada por IA
# --------------------------------------------------------------------------

SQL_OBJETO = """
SELECT o.*,
       (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = o.id)   AS n_colunas,
       (SELECT count(*) FROM catalogo.coluna c
         WHERE c.objeto_id = o.id AND c.embedding IS NOT NULL)             AS n_vetores,
       (SELECT count(*) FROM catalogo.amostra a WHERE a.objeto_id = o.id)  AS n_amostra,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.origem_tabela = o.nome)                                   AS fks_saindo,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.destino_tabela = o.nome)                                  AS fks_entrando
  FROM catalogo.objeto o
 WHERE o.nome = %s
"""

SQL_DESCRICAO = "SELECT * FROM catalogo.descricao_ia WHERE objeto_id = %s"

SQL_COLUNAS_DETALHE = """
SELECT posicao, nome, tipo_completo, aceita_nulo, eh_pk, valor_default, comentario,
       sensivel, sensivel_categoria, sensivel_motivo
  FROM catalogo.coluna WHERE objeto_id = %s ORDER BY posicao
"""

SQL_RESTRICOES_DETALHE = """
SELECT nome, tipo, colunas, ref_tabela, ref_colunas, delete_rule
  FROM catalogo.restricao WHERE objeto_id = %s ORDER BY tipo, nome
"""

SQL_INDICES_DETALHE = """
SELECT nome, unico, tipo, colunas
  FROM catalogo.indice WHERE objeto_id = %s ORDER BY nome
"""

SQL_AMOSTRA_DETALHE = """
SELECT linha, mascarada, dados
  FROM catalogo.amostra WHERE objeto_id = %s ORDER BY linha LIMIT 10
"""

CAMPOS_RESTRICOES = [
    ("nome", "Restrição", False),
    ("tipo", "Tipo", False),
    ("colunas", "Colunas", False),
    ("ref_tabela", "Referencia", False),
    ("ref_colunas", "Colunas ref.", False),
    ("delete_rule", "Delete rule", False),
]

CAMPOS_INDICES = [
    ("nome", "Índice", False),
    ("unico", "Único", False),
    ("tipo", "Tipo", False),
    ("colunas", "Colunas", False),
]

CAMPOS_AMOSTRA = [
    ("linha", "Linha", True),
    ("mascarada", "Mascarada", False),
    ("dados", "Dados", False),
]


def buscar_objeto(nome):
    return catalogo.um(SQL_OBJETO, (nome,), f"objeto {nome}")


def montar_colunas_detalhe(objeto, descricao):
    """Colunas do objeto, com a descricao da IA anexada quando existir."""
    linhas = catalogo.consultar(SQL_COLUNAS_DETALHE, (objeto["id"],), "colunas do objeto")
    por_nome = {}
    if descricao:
        por_nome = {campo["coluna"]: campo["descricao"] for campo in descricao["campos"]}

    campos = [
        ("posicao", "#", True),
        ("nome", "Coluna", False),
        ("tipo_completo", "Tipo", False),
        ("aceita_nulo", "Nulo", False),
        ("eh_pk", "PK", False),
        ("comentario", "Comentário", False),
    ]
    if por_nome:
        for linha in linhas:
            linha["ia"] = por_nome.get(linha["nome"])
        campos.append(("ia", "Descrição (IA)", False))

    # So aparece se ALGUMA coluna do objeto ja foi avaliada -- objeto inteiro sem
    # avaliacao nao ganha uma coluna vazia sugerindo que nada e sensivel.
    if any(linha["sensivel"] is not None for linha in linhas):
        for linha in linhas:
            # Nulo e "nao avaliada", nao "nao e sensivel": os dois precisam se
            # distinguir na tela, senao repetimos a garantia falsa do mascarada.
            if linha["sensivel"] is None:
                linha["sens"] = "não avaliada"
            elif linha["sensivel"]:
                linha["sens"] = f"⚠ {linha['sensivel_categoria']} — {linha['sensivel_motivo']}"
            else:
                linha["sens"] = "não"
        campos.append(("sens", "Sensível (IA)", False))
    return montar_tabela(campos, linhas)


def montar_vinculos(entrando, saindo, descricao):
    """As duas listas de vizinhos do painel Relacionamentos, COMPLETAS.

    Vem das FKs reais (catalogo.relacionamento), nao da descricao da IA: a IA
    escreve uma lista resumida -- em CAPADMISSION ela cita 25 dependentes dos 38
    que existem. O desenho ao lado ja mostra todos, mas so o nome; e aqui que
    aparecem a coluna da FK e o motivo que a IA escreveu, casado por nome.
    """
    def motivos(chave):
        # Um dicionario POR DIRECAO: tabela que aparece dos dois lados -- e comum,
        # CAPEVOLUTION aponta para CAPADMISSION e e apontada por ela -- tem um
        # motivo em cada sentido, e um dicionario so faria um sobrescrever o outro.
        if not descricao:
            return {}
        return {item["tabela"]: item.get("motivo") for item in descricao[chave]}

    def itens(vizinhos, chave):
        motivo_de = motivos(chave)
        return [
            {
                "tabela": v["vizinho"],
                "colunas": v["colunas"],
                "fks": v["fks"],
                "motivo": motivo_de.get(v["vizinho"]),
                "vazia": not v["tem_registros"],
            }
            for v in vizinhos
        ]

    # A ORDEM importa: a lista fica embaixo do desenho, e cada coluna tem de cair
    # sob o lado que ela descreve. Quem aponta para ca (entrando) e desenhado a
    # esquerda, entao "Dependem desta" vem primeiro. Invertido, o leitor ve
    # MATMATERIALMOV a esquerda no desenho e a direita na lista, e conclui que uma
    # das duas esta errada. A cor (`direcao`) e a mesma da aresta, pelo mesmo motivo.
    return [
        {
            "titulo": "Dependem desta",
            "icone": "arrow-down-left",
            "direcao": "entrando",
            "itens": itens(entrando, "dependentes"),
        },
        {
            "titulo": "Depende de",
            "icone": "arrow-up-right",
            "direcao": "saindo",
            "itens": itens(saindo, "dependencias"),
        },
    ]


def gerar_detalhe(nome, usuario=None, aviso=None):
    caminho = f"/oracle/objetos/{nome}"
    try:
        objeto = buscar_objeto(nome)
        if not objeto:
            return None, 404

        descricao = catalogo.um(SQL_DESCRICAO, (objeto["id"],), "descrição gravada")
        entrando, saindo = grafo.vizinhos(nome)
        restricoes = catalogo.consultar(
            SQL_RESTRICOES_DETALHE, (objeto["id"],), "restrições do objeto"
        )
        indices = catalogo.consultar(
            SQL_INDICES_DETALHE, (objeto["id"],), "índices do objeto"
        )
        amostra = catalogo.consultar(SQL_AMOSTRA_DETALHE, (objeto["id"],), "amostra do objeto")
    except catalogo.ConsultaFalhou as falha:
        return pagina_erro(falha, usuario, caminho)

    # Sem provedor cadastrado a pagina abre igual, so sem o botao
    try:
        pares = provedores.disponiveis()
        pares_vetor = provedores.disponiveis("embedding")
    except provedores.ConfiguracaoInvalida as erro:
        pares, pares_vetor = [], []
        aviso = aviso or {"motivo": erro.motivo, "detalhe": erro.detalhe}

    col_colunas, col_linhas = montar_colunas_detalhe(objeto, descricao)
    html = layout.render(
        "oracle_objeto.html",
        objeto["nome"],
        usuario,
        "/oracle/objetos",
        crumb="Oracle · Objetos",
        descricao_pagina=(
            (descricao and descricao["rotulo"])
            or objeto["comentario"]
            or "Sem comentário na origem."
        ),
        objeto=objeto,
        cards=montar_kpis_objeto(objeto),
        svg=grafo.desenhar(nome, entrando, saindo),
        legenda=grafo.legenda(entrando, saindo),
        vinculos=montar_vinculos(entrando, saindo, descricao),
        ia=descricao,
        ia_vencida=bool(descricao and descricao["gerado_em"] < objeto["atualizado_em"]),
        provedores=pares,
        provedores_vetor=pares_vetor,
        aviso=aviso,
        colunas=col_colunas,
        linhas=col_linhas,
        restricoes=montar_tabela(CAMPOS_RESTRICOES, restricoes),
        indices=montar_tabela(CAMPOS_INDICES, indices),
        amostra=montar_tabela(CAMPOS_AMOSTRA, amostra),
    )
    return html, 200


def montar_kpis_objeto(objeto):
    return [
        {
            "rotulo": "Registros",
            "valor": layout.fmt(objeto["num_registros"]),
            "hint": "com dados na amostra" if objeto["tem_registros"] else "tabela vazia",
        },
        {"rotulo": "Colunas", "valor": layout.fmt(objeto["n_colunas"]), "hint": ""},
        {
            "rotulo": "Relacionamentos",
            "valor": layout.fmt(objeto["fks_entrando"] + objeto["fks_saindo"]),
            "hint": f"{layout.fmt(objeto['fks_entrando'])} entrando · "
            f"{layout.fmt(objeto['fks_saindo'])} saindo",
        },
        {
            "rotulo": "Linhas de amostra",
            "valor": layout.fmt(objeto["n_amostra"]),
            "hint": "coletadas da tabela",
        },
    ]


def gerar_grafo(usuario=None):
    """Pagina da Visao Grafo. Os dados vem depois, por /oracle/grafo.json."""
    try:
        total = catalogo.um(
            f"SELECT count(*) AS total FROM ({grafo.ALVO}) alvo", (), "tamanho do grafo"
        )["total"]
    except catalogo.ConsultaFalhou as falha:
        return pagina_erro(falha, usuario, "/oracle/grafo")

    html = layout.render(
        "oracle_grafo.html",
        "Visão Grafo",
        usuario,
        "/oracle/grafo",
        crumb="Oracle",
        descricao=(
            "Começa pelas raízes do schema — tabelas com registros que são "
            "referenciadas por outras e não dependem de nenhuma. Clique num nó para "
            "abrir a árvore de quem depende dele."
        ),
        total=total,
    )
    return html, 200


# --------------------------------------------------------------------------
# Mapa semantico
#
# A consulta e o agrupamento vivem em src/mapa.py; aqui e so a pagina.
# --------------------------------------------------------------------------

MAPA = "/oracle/mapa"

# Quantas tabelas a busca traz para o mapa. Maior que o top 20 da tela de busca
# porque aqui o resultado nao e uma lista para ler linha a linha: e um desenho, e
# com 20 nos ele nao chega a formar bloco de assunto.
TOPK_MAPA = 50


def modelo_do_mapa():
    """Em que espaco vetorial desenhar. None quando nada foi vetorizado ainda.

    Escolhe o modelo com mais tabelas embutidas, e nao o provedor cadastrado em
    Setup: o mapa nao chama API nenhuma, entao o que manda e o que ESTA no banco.
    Um provedor trocado depois nao pode apagar o mapa dos vetores ja gravados.
    """
    espacos = busca.cobertura()
    if not espacos:
        return None
    return max(espacos, key=lambda espaco: espaco["objetos"])["modelo"]


def gerar_mapa(excluir="", termo="", topk=TOPK_MAPA, usuario=None):
    """Pagina do Mapa semantico. Os dados vem depois, por /oracle/mapa.json."""
    try:
        modelo = modelo_do_mapa()
    except catalogo.ConsultaFalhou as falha:
        return pagina_erro(falha, usuario, MAPA)

    html = layout.render(
        "oracle_mapa.html",
        "Mapa semântico",
        usuario,
        MAPA,  # canonico: o menu casa por href exato, e a URL vem com querystring
        crumb="Oracle",
        descricao=(
            "As tabelas posicionadas por significado, não por chave estrangeira. "
            "Blocos de cor são assuntos; a linha entre duas tabelas é o quanto "
            "elas falam da mesma coisa. Busque para desenhar só o que a busca "
            "trouxer."
        ),
        modelo=modelo,
        excluir=excluir,
        termo=termo,
        topk=topk,
        acao=MAPA,
    )
    return html, 200


def dados_do_mapa(excluir="", termo="", topk=TOPK_MAPA, par=None):
    """O JSON de /oracle/mapa.json. Devolve o recorte vazio quando nao ha vetor.

    Com `termo`, o mapa desenha SO as tabelas que a busca semantica trouxe -- a
    mesma busca da tela de busca, sem ranking proprio. Sem termo, desenha o
    recorte inteiro, como sempre fez.

    CUSTO: com termo isto vira uma chamada paga de embedding, dentro de
    busca.buscar(). Sem termo nao chama API nenhuma -- e por isso que o termo
    vazio continua valendo, e nao vira erro.
    """
    modelo = modelo_do_mapa()
    if not modelo:
        return {"nodes": [], "edges": [], "temas": [], "gemeas": [],
                "meta": {"modelo": None}}

    nomes, meta_busca = None, None
    if termo:
        # escopo "ambos": a tabela entra tanto pela propria descricao quanto por
        # um campo dela ter casado. E o que traz mais tabela pertinente.
        linhas, meta_busca = busca.buscar(termo, "ambos", topk, par, excluir)
        nomes = [linha["nome"] for linha in linhas]

    dados = mapa.mapa(modelo, excluir, nomes)
    dados["meta"]["termo"] = termo
    dados["meta"]["busca"] = meta_busca
    return dados


# --------------------------------------------------------------------------
# Busca semantica
#
# O ranking e a consulta vivem em src/busca.py; aqui e so a pagina.
# --------------------------------------------------------------------------

BUSCA = "/oracle/busca"

# Uma lista de campos por escopo -- o que a busca devolve muda com ele.
# O rotulo da IA e o porte (registros e colunas) aparecem em TODO escopo: o nome
# cru nao diz o que a tabela e, e uma tabela vazia ou de 3 colunas raramente e a
# que se procura -- sem esses numeros o resultado bem ranqueado ainda obriga a
# abrir uma por uma para descartar.
CAMPOS_BUSCA = {
    "tabelas": [
        ("nome", "Objeto", False),
        ("rotulo", "Rótulo (IA)", False),
        ("resumo", "Resumo (IA)", False),
        ("num_registros", "Registros", True),
        ("n_colunas", "Colunas", True),
        ("relevancia", "Relevância", True),
    ],
    "campos": [
        ("objeto", "Objeto", False),
        ("rotulo", "Rótulo (IA)", False),
        ("campo", "Campo", False),
        ("descricao", "Descrição (IA)", False),
        ("num_registros", "Registros", True),
        ("n_colunas", "Colunas", True),
        ("relevancia", "Relevância", True),
    ],
    "ambos": [
        ("nome", "Objeto", False),
        ("rotulo", "Rótulo (IA)", False),
        ("evidencia", "Campos que casaram", False),
        ("num_registros", "Registros", True),
        ("n_colunas", "Colunas", True),
        ("relevancia", "Relevância", True),
    ],
}

LINK_BUSCA = {
    "tabelas": ("nome", "/oracle/objetos/{}"),
    "campos": ("objeto", "/oracle/objetos/{}"),
    "ambos": ("nome", "/oracle/objetos/{}"),
}


def gerar_busca(termo="", escopo="ambos", topk=20, par=None, excluir="", usuario=None):
    """Pagina da busca semantica. Devolve (html, status_code).

    Termo vazio NAO chama a API -- a pagina abre so com o formulario. E a guarda
    de custo desta rota: como e um GET, um F5 repetiria a chamada paga.
    """
    escopo = escopo if escopo in busca.ESCOPOS else "ambos"
    termo = (termo or "").strip()
    aviso, linhas, meta = None, [], None

    try:
        pares = provedores.disponiveis("embedding")
        espacos = busca.cobertura()
    except catalogo.ConsultaFalhou as falha:
        return pagina_erro(falha, usuario, BUSCA)
    except provedores.ConfiguracaoInvalida as erro:
        pares, espacos = [], []
        aviso = {"motivo": erro.motivo, "detalhe": erro.detalhe}

    if termo and pares:
        try:
            linhas, meta = busca.buscar(termo, escopo, topk, par, excluir)
        except catalogo.ConsultaFalhou as falha:
            return pagina_erro(falha, usuario, BUSCA)
        except (embeddings.EmbutirFalhou, provedores.ConfiguracaoInvalida) as falha:
            aviso = {"motivo": falha.motivo, "detalhe": falha.detalhe}

    colunas, celulas = montar_tabela(
        CAMPOS_BUSCA[escopo], linhas, LINK_BUSCA[escopo]
    )
    html = layout.render(
        "oracle_busca.html",
        "Busca semântica",
        usuario,
        BUSCA,  # canonico: o menu casa por href exato, e a URL vem com querystring
        crumb="Oracle",
        descricao=(
            "Procura por significado, não por nome. Encontra só o que foi vetorizado "
            "em Setup › Lote de vetores."
        ),
        colunas=colunas,
        linhas=celulas,
        termo=termo,
        excluir=excluir,
        escopo=escopo,
        escopos=busca.ESCOPOS,
        topk=topk,
        pares=pares,
        par=par or "",
        espacos=espacos,
        meta=meta,
        aviso=aviso,
        acao=BUSCA,
    )
    return html, 200
