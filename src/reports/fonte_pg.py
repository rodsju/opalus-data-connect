"""Backend Postgres dos /reports: consultas sobre a carga ativa da Conciliação."""

from ..conciliacao import banco
from . import sql_pg


def rodar(nome, params, limite=None):
    sql = sql_pg.CONSULTAS[nome]
    binds = {"DT_INI": None, "DT_FIM": None, "UNIDADE": None, "CONVENIO": None, "MOTIVO": None, "TIPO": None,
             **(params or {})}
    if limite:
        sql = f"{sql.rstrip()}\n LIMIT {int(limite)}"
    return banco.consultar(sql, binds, f"reports {nome}")
