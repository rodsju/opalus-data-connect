import pytest

from src.conciliacao import privacidade


def test_codigo_invalido_recusado():
    for codigo in ["", "abc", "P", "P12a", "X123", "1' OR 1=1"]:
        with pytest.raises(ValueError):
            privacidade.nome_paciente(codigo)


def test_sem_permissao_nao_consulta(monkeypatch):
    monkeypatch.setattr(privacidade, "pode_ver_nome", lambda u: False)
    with pytest.raises(PermissionError):
        privacidade.nome_paciente("P123")


def test_codigo_erp_busca_no_oracle(monkeypatch):
    from src.reports import fonte
    chamadas = []
    monkeypatch.setattr(fonte, "rodar", lambda nome, p, limite=None: chamadas.append((nome, p)) or [{"nome": " FULANO "}])
    assert privacidade.nome_paciente("p123") == "FULANO"
    assert chamadas == [("paciente_nome", {"ID": 123})]


def test_macro_mascara_e_nao_leva_nome():
    from src.layout import env
    html = env.from_string('{% import "reports/_macros.html" as rp %}{{ rp.nome_paciente("P123") }}{{ rp.codigo_paciente("P123") }}').render()
    assert 'data-paciente="P123"' in html and "*****" in html
