"""O schema em uso: o pre-filtro de todas as telas do catalogo.

Sempre ha UM schema escolhido -- nao existe "todos". O catalogo liga tabelas pelo
nome (relacionamento.origem_tabela = objeto.nome, /oracle/objetos/<nome>), e duas
tabelas de mesmo nome em schemas diferentes se misturariam. A comparacao entre
schemas fica no resumo da visao geral (resumo()).

A escolha mora no cookie `esquema` e e resolvida UMA vez por request pelo
middleware de src/main.py, que a guarda num ContextVar. As funcoes de dados
recebem o esquema_id explicito; quem le atual() sao as gerar_* e o layout.
"""

import contextvars
import logging

from . import catalogo

logger = logging.getLogger(__name__)

COOKIE = "esquema"
# Um ano: a escolha vale "ate o usuario trocar", nao ate fechar o navegador
COOKIE_MAX_AGE = 365 * 24 * 3600

SQL_LISTAR = """
SELECT e.id, e.nome, s.nome AS servidor, s.tipo AS servidor_tipo
  FROM catalogo.esquema e
  JOIN catalogo.servidor s ON s.id = e.servidor_id
 ORDER BY s.nome, e.nome
"""

SQL_RESUMO = """
SELECT e.id, e.nome, s.nome AS servidor,
       count(o.id)                                         AS objetos,
       count(o.id) FILTER (WHERE o.tipo = 'TABLE')         AS tabelas,
       count(o.id) FILTER (WHERE o.tipo = 'VIEW')          AS views,
       count(o.id) FILTER (WHERE o.tem_registros)          AS com_registros,
       -- ::int porque sum() devolve numeric e a tela exibiria "52.975,00"
       coalesce(sum((SELECT count(*) FROM catalogo.coluna c
                      WHERE c.objeto_id = o.id)), 0)::int  AS colunas,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.esquema_id = e.id)                        AS relacionamentos,
       count(d.objeto_id)                                  AS descritos,
       count(o.id) FILTER (WHERE o.embedding IS NOT NULL)  AS vetorizados,
       max(o.atualizado_em)                                AS atualizado_em
  FROM catalogo.esquema e
  JOIN catalogo.servidor s ON s.id = e.servidor_id
  LEFT JOIN catalogo.objeto o ON o.esquema_id = e.id
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
 GROUP BY e.id, e.nome, s.nome
 ORDER BY s.nome, e.nome
"""

_atual = contextvars.ContextVar("esquema_atual", default=None)
_lista = contextvars.ContextVar("esquemas_lista", default=None)


def listar():
    return catalogo.consultar(SQL_LISTAR, (), "schemas do catálogo")


def resumo():
    return catalogo.consultar(SQL_RESUMO, (), "resumo por schema")


def escolher(lista, cookie):
    """O schema do cookie, se ainda existe; senao o primeiro. None se nao ha nenhum.

    Cookie invalido ou de schema apagado cai no padrao sem erro: e uma preferencia,
    nao uma ordem.
    """
    if not lista:
        return None
    try:
        pedido = int(cookie)
    except (TypeError, ValueError):
        pedido = None
    for esquema in lista:
        if esquema["id"] == pedido:
            return esquema
    return lista[0]


def resolver(cookie):
    """Le a lista e fixa o schema deste request. Falha no banco nao derruba a
    pagina aqui: quem consulta o catalogo mostra o erro do jeito dela."""
    try:
        lista = listar()
    except catalogo.ConsultaFalhou:
        lista = []
    _lista.set(lista)
    esquema = escolher(lista, cookie)
    _atual.set(esquema)
    return esquema


def atual():
    """{id, nome, servidor} do schema em uso, ou None se o catalogo nao tem schema."""
    return _atual.get()


def atual_id():
    esquema = atual()
    return esquema["id"] if esquema else None


def lista_atual():
    return _lista.get() or []


def rotulo(esquema):
    return f"{esquema['servidor']} · {esquema['nome']}" if esquema else "sem schema"


def destino_seguro(voltar):
    """Para onde voltar depois de trocar o schema. So caminho local -- `//host`
    seria um redirect para fora -- e nunca a pagina de um objeto, que pode nao
    existir no schema novo."""
    voltar = (voltar or "").strip()
    if not voltar.startswith("/") or voltar.startswith("//") or "\\" in voltar:
        return "/oracle"
    if voltar.startswith("/oracle/objetos/"):
        return "/oracle/objetos"
    return voltar
