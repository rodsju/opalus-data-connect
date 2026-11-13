"""Login IAM do Cloud SQL: o token da SA vai como senha só com DB_IAM_AUTH."""

import psycopg

from src import catalogo


def _capturar(monkeypatch):
    chamadas = []
    monkeypatch.setattr(psycopg, "connect", lambda dsn, **kw: chamadas.append((dsn, kw)))
    return chamadas


def test_iam_manda_o_token_como_senha(monkeypatch):
    chamadas = _capturar(monkeypatch)
    monkeypatch.setattr(catalogo, "IAM", True)
    monkeypatch.setattr(catalogo, "_token", lambda: "tok")
    catalogo.conectar("postgresql://sa%40p.iam@h/db")
    assert chamadas == [("postgresql://sa%40p.iam@h/db", {"connect_timeout": 5, "password": "tok"})]


def test_sem_iam_usa_so_o_dsn(monkeypatch):
    chamadas = _capturar(monkeypatch)
    monkeypatch.setattr(catalogo, "IAM", False)
    catalogo.conectar()
    assert chamadas == [(catalogo.DSN, {"connect_timeout": 5})]
