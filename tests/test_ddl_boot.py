"""Retentativa do DDL no boot.

Regressao de hml (25/11/2026): o boot tentou uma vez so, deu `connection timeout
expired` enquanto a rede da VPC ainda subia, e a tabela nova do deploy nao foi
criada -- com o app conectando normal segundos depois.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import catalogo  # noqa: E402


def _roteiro(monkeypatch, respostas):
    chamadas = []

    def falso(contexto="no boot", registrar_falha=True):
        chamadas.append(registrar_falha)
        return respostas[len(chamadas) - 1]

    monkeypatch.setattr(catalogo, "aplicar_ddl", falso)
    return chamadas


def test_repete_ate_conectar(monkeypatch):
    chamadas = _roteiro(monkeypatch, [(False, "connection timeout expired")] * 2 + [(True, "80 ms")])
    esperas = []
    assert catalogo.aplicar_ddl_no_boot(tentativas=5, espera=5, dormir=esperas.append) == (True, "80 ms")
    assert len(chamadas) == 3
    assert esperas == [5, 10]  # cresce a cada tentativa


def test_desiste_na_ultima_e_so_ela_registra_erro(monkeypatch):
    chamadas = _roteiro(monkeypatch, [(False, "syntax error")] * 3)
    ok, detalhe = catalogo.aplicar_ddl_no_boot(tentativas=3, espera=0, dormir=lambda s: None)
    assert (ok, detalhe) == (False, "syntax error")
    # ERROR com traceback so na ultima; as anteriores saem como WARNING
    assert chamadas == [False, False, True]
