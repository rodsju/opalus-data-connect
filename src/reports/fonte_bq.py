"""Backend BigQuery dos /reports: lê a camada bronze (cópia das tabelas do ERP).

Configuração só por variável de ambiente -- o dataset muda entre ambientes e
entre camadas, então nunca fica escrito nas SQLs:

    BQ_PROJECT   projeto dos dados e dos jobs (ex.: atlas-dw-hml-511718)
    BQ_DATASET   dataset das tabelas do ERP (ex.: bronze_iw_opalus)
    BQ_LOCATION  região dos jobs (opcional; ex.: us-central1)
    BQ_TIMEOUT   segundos por consulta (default 90)

Credencial: ADC (GOOGLE_APPLICATION_CREDENTIALS ou gcloud auth application-default login).
"""

import datetime
import os
import re
import threading

from . import sql_bq

NOME_DE_PROJETO = re.compile(r"^[a-z][a-z0-9-]{4,29}$")
NOME_DE_DATASET = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")

# NULL precisa de tipo no BigQuery, então o tipo vem do nome do bind, não do valor.
TIPOS_BIND = {
    "DT_INI": "DATETIME",
    "DT_FIM": "DATETIME",
    "UNIDADE": "STRING",
    "CONVENIO": "STRING",
    "MOTIVO": "STRING",
    "TIPO": "INT64",
    "CATEGORIA": "INT64",
    "ID": "INT64",
    "ADMISSAO": "INT64",
    "ORCAMENTO": "INT64",
    "IDS": "INT64",
    "SENHAS": "STRING",
    "PROTOCOLOS": "STRING",
    "COMPETENCIAS": "STRING",
    "TABELAS": "STRING",
    "LIMITE_REPORTS": "INT64",
}


class BqIndisponivel(Exception):
    """Não deu para falar com o BigQuery. `dica` diz o que provavelmente está errado."""

    def __init__(self, motivo, dica=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.dica = dica


class NaoMigrada(Exception):
    """A consulta existe no Oracle mas ainda não tem versão em sql_bq.py."""

    def __init__(self, nome):
        super().__init__(f"consulta '{nome}' ainda não migrada para o BigQuery")
        self.motivo = str(self)
        self.dica = "falta portar a SQL para src/reports/sql_bq.py"


def _config():
    faltando = [chave for chave in ("BQ_PROJECT", "BQ_DATASET") if not os.getenv(chave, "").strip()]
    if faltando:
        raise BqIndisponivel("BigQuery não configurado", "faltam no ambiente: " + ", ".join(faltando))
    projeto = os.getenv("BQ_PROJECT").strip()
    dataset = os.getenv("BQ_DATASET").strip()
    if not NOME_DE_PROJETO.match(projeto):
        raise BqIndisponivel("BQ_PROJECT inválido", repr(projeto))
    if not NOME_DE_DATASET.match(dataset):
        raise BqIndisponivel("BQ_DATASET inválido", repr(dataset))
    return {
        "projeto": projeto,
        "dataset": dataset,
        "location": os.getenv("BQ_LOCATION", "").strip() or None,
        "timeout": float(os.getenv("BQ_TIMEOUT") or "90"),
    }


def destino():
    """`projeto.dataset` configurado, para a tela de health. Sem levantar."""
    try:
        cfg = _config()
    except BqIndisponivel as erro:
        return erro.dica or erro.motivo
    return f"{cfg['projeto']}.{cfg['dataset']}"


_cliente = None
_cliente_chave = None
_trava = threading.Lock()


def _cliente_para(cfg):
    """Um client por processo (é thread-safe); recria se projeto/região mudarem."""
    global _cliente, _cliente_chave
    chave = (cfg["projeto"], cfg["location"])
    with _trava:
        if _cliente is None or _cliente_chave != chave:
            from google.auth.exceptions import DefaultCredentialsError
            from google.cloud import bigquery

            try:
                _cliente = bigquery.Client(project=cfg["projeto"], location=cfg["location"])
            except DefaultCredentialsError as erro:
                raise BqIndisponivel(
                    "credencial do Google não encontrada",
                    f"rode: gcloud auth application-default login --project={cfg['projeto']}",
                ) from erro
            _cliente_chave = chave
        return _cliente


def qualificar(sql, cfg):
    """Troca {ds} pelo dataset configurado, entre crases."""
    return sql.replace("{ds}", f"`{cfg['projeto']}.{cfg['dataset']}`")


def _valor(tipo, valor):
    # Os filtros mandam datetime.date; a coluna é DATETIME e o BQ não converte sozinho.
    if tipo == "DATETIME" and isinstance(valor, datetime.date) and not isinstance(valor, datetime.datetime):
        return datetime.datetime.combine(valor, datetime.time())
    if tipo == "INT64" and valor is not None:
        return int(valor)
    return valor


def parametros(sql, params):
    """QueryParameters para os @BINDS que a SQL usa, tipados por TIPOS_BIND."""
    from google.cloud import bigquery

    saida = []
    for nome, valor in (params or {}).items():
        if not re.search(rf"@{nome}\b", sql):
            continue
        tipo = TIPOS_BIND.get(nome)
        if tipo is None:
            raise ValueError(f"bind @{nome} sem tipo em fonte_bq.TIPOS_BIND")
        if isinstance(valor, (list, tuple, set)):
            saida.append(bigquery.ArrayQueryParameter(nome, tipo, [_valor(tipo, v) for v in valor]))
        else:
            saida.append(bigquery.ScalarQueryParameter(nome, tipo, _valor(tipo, valor)))
    return saida


def executar(sql, params=None, cfg=None):
    """Roda SQL já qualificada; devolve list[dict] com chaves em minúsculo."""
    from google.api_core import exceptions as gexc
    from google.auth import exceptions as aexc
    from google.cloud import bigquery

    cfg = cfg or _config()
    cliente = _cliente_para(cfg)
    job_config = bigquery.QueryJobConfig(
        query_parameters=parametros(sql, params),
        job_timeout_ms=int(cfg["timeout"] * 1000),
    )
    try:
        job = cliente.query(sql, job_config=job_config)
        linhas = job.result(timeout=cfg["timeout"])
    except aexc.RefreshError as erro:
        raise BqIndisponivel(
            "credencial do Google expirada ou revogada",
            f"rode: gcloud auth application-default login --project={cfg['projeto']}",
        ) from erro
    except gexc.Forbidden as erro:
        raise BqIndisponivel(
            f"sem permissão em {cfg['projeto']}.{cfg['dataset']}",
            "a conta do ADC precisa de BigQuery Job User e Data Viewer",
        ) from erro
    except gexc.NotFound as erro:
        raise BqIndisponivel(
            f"tabela ou dataset não encontrado em {cfg['projeto']}.{cfg['dataset']}",
            "confira BQ_DATASET",
        ) from erro
    return [{chave.lower(): valor for chave, valor in linha.items()} for linha in linhas]


def rodar(nome, params, limite=None):
    """Executa a consulta `nome` de sql_bq.CONSULTAS; devolve list[dict]."""
    if nome not in sql_bq.CONSULTAS:
        raise NaoMigrada(nome)
    cfg = _config()
    sql = qualificar(sql_bq.CONSULTAS[nome], cfg)
    params = dict(params or {})
    if limite:
        # LIMIT no fim, não num SELECT externo: o BigQuery não garante a ordem de subconsulta.
        sql = f"{sql.rstrip()}\nLIMIT @LIMITE_REPORTS"
        params["LIMITE_REPORTS"] = int(limite)
    return executar(sql, params, cfg)


def rodar_formulario(tabela, ids):
    """Formulários de evolução (TD*): ainda não migrado."""
    raise NaoMigrada(f"formulario {tabela}")
