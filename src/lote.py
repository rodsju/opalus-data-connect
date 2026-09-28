"""Lote de IA: selecao das tabelas, criacao do job e progresso.

Duas tarefas passam por aqui: gerar a descricao e vetorizar o texto dela. O que
muda entre elas e o que cada item faz e quanto custa -- fila, retomada,
cancelamento e paralelismo sao os mesmos, entao a maquinaria e uma so.

Quem executa e scripts/descrever_lote.py, um processo destacado -- uma tabela leva
56s na mediana, entao o lote completo passa de seis horas e nao cabe nem num request
nem numa thread do uvicorn, que reinicia a cada arquivo salvo.

Este modulo e a interface com o banco; o script consome as mesmas funcoes.
"""

import json
import logging
import os
import subprocess
import sys

from . import catalogo

logger = logging.getLogger(__name__)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(RAIZ, "scripts", "descrever_lote.py")

TAREFAS = ("descricao", "embedding", "mascara")

# Custo por tabela, so para estimar antes de disparar. A descricao vem das
# medianas do que ja foi gerado; o embedding e outra ordem de grandeza -- uma
# chamada curta, sem token de saida, com os campos todos num lote so.
CUSTO = {
    "descricao": {"segundos": 56, "entrada": 2_217, "saida": 9_029},
    "embedding": {"segundos": 3, "entrada": 1_500, "saida": 0},
    # Mascara: a chamada leva um PACOTE de colunas, nao uma tabela. Medido em
    # pacote de 50 (34,1s, 1.969 entrada, 5.157 saida) e rateado pelas ~20 colunas
    # com descricao que um objeto tem neste catalogo -- 0,4 pacote por objeto.
    "mascara": {"segundos": 14, "entrada": 787, "saida": 2_063},
}

SEM_DESCRICAO = (
    "NOT EXISTS (SELECT 1 FROM catalogo.descricao_ia d WHERE d.objeto_id = o.id)"
)
COM_DESCRICAO = (
    "EXISTS (SELECT 1 FROM catalogo.descricao_ia d WHERE d.objeto_id = o.id)"
)
# Vetorizar so faz sentido sobre texto ja gerado: sem descricao nao ha o que
# vetorizar, e a tabela entraria no lote so para falhar.
SEM_VETOR = f"o.embedding IS NULL AND {COM_DESCRICAO}"
# Classificar so faz sentido sobre coluna que ja tem descricao: e ela o insumo do
# julgamento. `sensivel IS NULL` e "nao avaliada" -- que nao e "nao e sensivel".
SEM_CLASSIFICACAO = (
    "EXISTS (SELECT 1 FROM catalogo.coluna c WHERE c.objeto_id = o.id"
    " AND c.descricao_ia IS NOT NULL AND c.descricao_ia <> '' AND c.sensivel IS NULL)"
)
COM_DEPENDENTES = (
    "EXISTS (SELECT 1 FROM catalogo.relacionamento r WHERE r.destino_tabela = o.nome)"
)
COM_DEPENDENCIAS = (
    "EXISTS (SELECT 1 FROM catalogo.relacionamento r WHERE r.origem_tabela = o.nome)"
)

# (chave, nome na querystring, rotulo, predicado)
FILTROS = (
    ("registros", "com_registros", "Só com registros", "o.tem_registros"),
    ("sem_descricao", "sem_descricao", "Só sem descrição", SEM_DESCRICAO),
    ("sem_vetor", "sem_vetor", "Só sem vetor", SEM_VETOR),
    ("sem_classificacao", "sem_classificacao", "Só com coluna não avaliada",
     SEM_CLASSIFICACAO),
    ("dependentes", "dependentes", "Só com dependentes", COM_DEPENDENTES),
    ("dependencias", "dependencias", "Só com dependências", COM_DEPENDENCIAS),
)


class LoteInvalido(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


# --------------------------------------------------------------------------
# Selecao
# --------------------------------------------------------------------------


def _onde(ativos, termo):
    condicoes = [pred for chave, _, _, pred in FILTROS if chave in ativos]
    params = []
    if termo:
        condicoes.append("o.nome ILIKE %s")
        params.append(f"%{termo}%")
    return (" WHERE " + " AND ".join(condicoes) if condicoes else ""), tuple(params)


def candidatas(ativos=(), termo="", limite=200, tarefa="descricao"):
    """Tabelas do recorte, com o total antes do limite de exibicao.

    A coluna de situacao muda com a tarefa: num lote de vetores o que importa e
    ter vetor, nao ter descricao.
    """
    onde, params = _onde(ativos, termo)
    origem = f"catalogo.objeto o{onde}"

    total = catalogo.um(
        f"SELECT count(*) AS total FROM {origem}", params, "candidatas do lote"
    )["total"]
    linhas = catalogo.consultar(
        f"""SELECT o.id, o.nome, o.num_registros,
                   (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = o.id)
                       AS n_colunas,
                   EXISTS (SELECT 1 FROM catalogo.descricao_ia d
                            WHERE d.objeto_id = o.id) AS descrita,
                   o.embedding IS NOT NULL AS vetorizada,
                   NOT EXISTS (SELECT 1 FROM catalogo.coluna c
                                WHERE c.objeto_id = o.id
                                  AND c.descricao_ia IS NOT NULL
                                  AND c.descricao_ia <> ''
                                  AND c.sensivel IS NULL) AS classificada
              FROM {origem}
             ORDER BY o.nome LIMIT {int(limite)}""",
        params,
        "listagem de candidatas",
    )
    return linhas, total


def ids_do_recorte(ativos, termo):
    """Todos os ids do filtro -- o "marcar todas as N" nao passa pela paginacao."""
    onde, params = _onde(ativos, termo)
    linhas = catalogo.consultar(
        f"SELECT o.id FROM catalogo.objeto o{onde} ORDER BY o.nome", params, "ids do lote"
    )
    return [linha["id"] for linha in linhas]


def estimativa(quantas, paralelismo, tarefa="descricao"):
    custo = CUSTO[tarefa]
    segundos = quantas * custo["segundos"] / max(1, paralelismo)
    return {
        "tabelas": quantas,
        "duracao": _duracao(segundos),
        "tokens_entrada": quantas * custo["entrada"],
        "tokens_saida": quantas * custo["saida"],
    }


def _duracao(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos}s"
    if segundos < 3600:
        return f"{segundos // 60}min"
    return f"{segundos // 3600}h{(segundos % 3600) // 60:02d}"


# --------------------------------------------------------------------------
# Criacao e disparo
# --------------------------------------------------------------------------

# Por tarefa, nao global: um lote de descricao e um de vetores batem em modelos
# diferentes e nao disputam o mesmo limite de requisicoes.
SQL_EM_ANDAMENTO = """
SELECT id FROM catalogo.lote_ia
 WHERE status IN ('pendente', 'rodando') AND tarefa = %s LIMIT 1
"""


def em_andamento(tarefa="descricao"):
    return catalogo.um(SQL_EM_ANDAMENTO, (tarefa,), f"lote de {tarefa} em andamento")


def criar(provedor, modelo, paralelismo, objetos, filtro, usuario=None, tarefa="descricao"):
    """Grava o cabecalho e um item por tabela. Devolve o id do lote."""
    if tarefa not in TAREFAS:
        raise LoteInvalido(f"Tarefa desconhecida: {tarefa}")
    if not objetos:
        raise LoteInvalido("Nenhuma tabela selecionada")
    aberto = em_andamento(tarefa)
    if aberto:
        raise LoteInvalido(
            f"O lote #{aberto['id']} ainda está em andamento",
            "Espere ele terminar ou cancele antes de abrir outro — dois lotes "
            "concorrentes só multiplicam o risco de limite de requisições.",
        )

    lote = catalogo.um(
        """INSERT INTO catalogo.lote_ia
               (tarefa, provedor, modelo, paralelismo, filtro, criado_por)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (tarefa, provedor, modelo, paralelismo, json.dumps(filtro), usuario),
        "criação do lote",
    )["id"]

    catalogo.executar(
        """INSERT INTO catalogo.lote_ia_item (lote_id, objeto_id)
           SELECT %s, unnest(%s::bigint[])
           ON CONFLICT DO NOTHING""",
        (lote, list(objetos)),
        f"itens do lote {lote}",
    )
    logger.info("lote %s de %s criado com %s tabelas", lote, tarefa, len(objetos))
    return lote


def disparar(lote_id, retomar=False):
    """Sobe o script como sessao propria, para sobreviver ao reload do uvicorn."""
    comando = [sys.executable, SCRIPT, "--job", str(int(lote_id))]
    if retomar:
        comando.append("--retomar")
    processo = subprocess.Popen(  # noqa: S603 - argumentos fixos, id e int
        comando,
        cwd=RAIZ,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info("lote %s disparado no pid %s", lote_id, processo.pid)
    return processo.pid


# --------------------------------------------------------------------------
# Progresso
# --------------------------------------------------------------------------

SQL_LOTE = "SELECT * FROM catalogo.lote_ia WHERE id = %s"

SQL_CONTAGEM = """
SELECT status, count(*) AS quantas,
       sum(tokens_entrada) AS entrada, sum(tokens_saida) AS saida
  FROM catalogo.lote_ia_item WHERE lote_id = %s GROUP BY status
"""

SQL_FALHAS = """
SELECT o.nome, i.erro, i.terminado_em
  FROM catalogo.lote_ia_item i JOIN catalogo.objeto o ON o.id = i.objeto_id
 WHERE i.lote_id = %s AND i.status = 'falhou'
 ORDER BY i.terminado_em DESC LIMIT 50
"""

SQL_LISTAR = """
SELECT l.id, l.tarefa, l.provedor, l.modelo, l.paralelismo, l.status,
       l.criado_em, l.terminado_em,
       (SELECT count(*) FROM catalogo.lote_ia_item i WHERE i.lote_id = l.id) AS itens,
       (SELECT count(*) FROM catalogo.lote_ia_item i
         WHERE i.lote_id = l.id AND i.status = 'concluido')                  AS concluidos
  FROM catalogo.lote_ia l ORDER BY l.id DESC LIMIT 20
"""


def buscar(lote_id):
    return catalogo.um(SQL_LOTE, (lote_id,), f"lote {lote_id}")


def listar():
    return catalogo.consultar(SQL_LISTAR, (), "lotes")


def progresso(lote_id):
    linhas = catalogo.consultar(SQL_CONTAGEM, (lote_id,), f"progresso do lote {lote_id}")
    por_status = {linha["status"]: linha["quantas"] for linha in linhas}
    total = sum(por_status.values())
    feitos = por_status.get("concluido", 0) + por_status.get("falhou", 0)
    return {
        "total": total,
        "pendente": por_status.get("pendente", 0),
        "rodando": por_status.get("rodando", 0),
        "concluido": por_status.get("concluido", 0),
        "falhou": por_status.get("falhou", 0),
        "feitos": feitos,
        "percentual": round(feitos * 100 / total) if total else 0,
        "tokens_entrada": sum(linha["entrada"] or 0 for linha in linhas),
        "tokens_saida": sum(linha["saida"] or 0 for linha in linhas),
    }


def falhas(lote_id):
    return catalogo.consultar(SQL_FALHAS, (lote_id,), f"falhas do lote {lote_id}")


def cancelar(lote_id):
    catalogo.executar(
        """UPDATE catalogo.lote_ia SET status = 'cancelado', terminado_em = now()
            WHERE id = %s AND status IN ('pendente', 'rodando')""",
        (lote_id,),
        f"cancelamento do lote {lote_id}",
    )
