"""Partes puras de Setup > Importar dados: validacao, argumentos do mapeador,
corpo do run do Cloud Run Job e a template."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src import importacao, layout  # noqa: E402


def _form(**campos):
    return {"modo": "completo", **campos}


# --------------------------------------------------------------------------
# Validacao do formulario
# --------------------------------------------------------------------------


def test_padroes_do_formulario_sao_os_do_script():
    modo, p = importacao.parametros_do_form(_form())
    assert modo == "completo"
    assert p == {"tabelas": None, "limite": None, "amostra": 100, "timeout": 60,
                 "contagem_exata": False, "sem_views": False, "pular_existentes": False}


def test_amostra_zero_vale_no_completo():
    _, p = importacao.parametros_do_form(_form(amostra="0"))
    assert p["amostra"] == 0


def test_so_amostras_recusa_amostra_zero():
    with pytest.raises(importacao.ImportacaoInvalida):
        importacao.parametros_do_form(_form(modo="amostras", amostra="0"))


def test_so_amostras_recusa_pular_existentes():
    # Pularia o schema inteiro sem fazer nada (ver o comentario do Makefile)
    with pytest.raises(importacao.ImportacaoInvalida):
        importacao.parametros_do_form(_form(modo="amostras", pular_existentes="1"))


@pytest.mark.parametrize("campos", [
    {"modo": "tudo"},
    {"limite": "0"},
    {"limite": "abc"},
    {"timeout": "9999"},
    {"amostra": "-1"},
])
def test_valores_invalidos_sao_recusados(campos):
    with pytest.raises(importacao.ImportacaoInvalida):
        importacao.parametros_do_form(_form(**campos))


# --------------------------------------------------------------------------
# Argumentos do mapeador
# --------------------------------------------------------------------------


def _imp(modo="completo", **parametros):
    _, p = importacao.parametros_do_form(_form(modo=modo, **parametros))
    return {"id": 7, "esquema_id": 3, "modo": modo, "parametros": p}


def test_argumentos_do_completo_padrao():
    assert importacao.argumentos(_imp()) == [
        "--importacao", "7", "--esquema-id", "3", "--amostra", "100", "--timeout", "60",
    ]


def test_argumentos_com_todas_as_opcoes():
    args = importacao.argumentos(_imp(
        tabelas="CAP%,GLB%", limite="3", contagem_exata="1", sem_views="1",
        pular_existentes="1",
    ))
    assert args[args.index("--tabelas") + 1] == "CAP%,GLB%"
    assert args[args.index("--limite") + 1] == "3"
    assert {"--contagem-exata", "--sem-views", "--pular-existentes"} <= set(args)
    assert "--somente-amostras" not in args


def test_so_amostras_vira_somente_amostras():
    assert "--somente-amostras" in importacao.argumentos(_imp(modo="amostras"))


def test_argumentos_batem_com_o_parser_do_mapeador():
    """O que a tela monta o mapeador tem de aceitar -- e entender do mesmo jeito."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
    import mapear_oracle

    args = mapear_oracle.montar_argumentos(importacao.argumentos(_imp(
        modo="amostras", tabelas="PAC%", limite="5", amostra="50",
    )))
    assert (args.importacao, args.esquema_id) == (7, 3)
    assert args.somente_amostras and args.tabelas == "PAC%"
    assert (args.limite, args.amostra) == (5, 50)


def test_override_repoe_o_script_na_frente():
    # O override de args SUBSTITUI os do job: sem o script, o python receberia
    # --importacao como nome de arquivo
    corpo = importacao.corpo_do_run(["--importacao", "7"])
    container = corpo["overrides"]["containerOverrides"][0]
    assert container["args"] == ["scripts/mapear_oracle.py", "--importacao", "7"]
    assert corpo["overrides"]["taskCount"] == 1


# --------------------------------------------------------------------------
# Ambiente
# --------------------------------------------------------------------------


def _sem_cloud_run(monkeypatch):
    for nome in ("K_SERVICE", "CLOUD_RUN_JOB", "IMPORT_JOB", "REGION"):
        monkeypatch.delenv(nome, raising=False)


def test_local_sempre_pode(monkeypatch):
    _sem_cloud_run(monkeypatch)
    assert importacao.disponivel() == (True, "")


def test_cloud_run_sem_job_fica_indisponivel(monkeypatch):
    _sem_cloud_run(monkeypatch)
    monkeypatch.setenv("K_SERVICE", "atlas-connect")
    monkeypatch.setenv("PROJECT_ID", "atlas-dw-prd-511718")
    pronto, motivo = importacao.disponivel()
    assert not pronto and "IMPORT_JOB" in motivo


def test_cloud_run_com_job(monkeypatch):
    _sem_cloud_run(monkeypatch)
    monkeypatch.setenv("K_SERVICE", "atlas-connect")
    monkeypatch.setenv("PROJECT_ID", "atlas-dw-hml-511718")
    monkeypatch.setenv("REGION", "us-central1")
    monkeypatch.setenv("IMPORT_JOB", "atlas-connect-import")
    assert importacao.disponivel() == (True, "")
    assert importacao.url_do_job() == (
        "https://run.googleapis.com/v2/projects/atlas-dw-hml-511718"
        "/locations/us-central1/jobs/atlas-connect-import"
    )


def test_percentual():
    assert importacao.percentual({"status": "rodando", "total": 200, "processados": 50}) == 25
    assert importacao.percentual({"status": "rodando", "total": None, "processados": 0}) == 0
    assert importacao.percentual({"status": "concluida", "total": 0, "processados": 0}) == 100


# --------------------------------------------------------------------------
# Template
# --------------------------------------------------------------------------

CONTEXTO = {
    "origens": [{"id": 1, "nome": "DBIWGERIATRICS", "servidor": "IW (homolog)"}],
    "modos": importacao.MODOS,
    "valores": {},
    "aberta": None,
    "recentes": [],
    "pronto": True,
    "motivo": "",
    "onde": "processo local destacado",
    "timeout_maximo": importacao.TIMEOUT_MAXIMO,
    "aviso": None,
    "sucesso": None,
}


def _renderizar(**mudancas):
    return layout.render("setup_importar.html", "Importar dados", None, "/setup/importar",
                         **{**CONTEXTO, **mudancas})


def test_form_oferece_as_opcoes_e_dispara():
    html = _renderizar()
    for trecho in ('value="completo"', 'value="amostras"', 'formaction="/setup/importar/testar"',
                   'formaction="/setup/importar/ddl"', "Disparar importação",
                   'name="pular_existentes"', 'name="contagem_exata"', 'name="sem_views"'):
        assert trecho in html


def test_sem_job_nao_mostra_o_disparo():
    html = _renderizar(pronto=False, motivo="Sem o job neste ambiente.")
    assert "Sem o job neste ambiente." in html
    assert "Disparar importação" not in html


def test_com_importacao_aberta_nao_mostra_o_disparo():
    html = _renderizar(aberta={"id": 4, "esquema": "DBIWGERIATRICS"})
    assert 'href="/setup/importar/4"' in html
    assert "Disparar importação" not in html


def test_menu_tem_o_item():
    assert any(item["href"] == "/setup/importar"
               for grupo in layout.MENU for item in grupo["itens"])


def test_progresso_renderiza_e_oferece_cancelar():
    imp = {"id": 4, "status": "rodando", "modo": "completo", "processados": 10, "total": 40,
           "objeto_atual": "CAPADMISSION", "heartbeat_em": None, "solicitada_em": None,
           "solicitada_por": "a@b", "iniciada_em": None, "concluida_em": None,
           "erros": ["aviso"], "execucao": "pid:1", "parametros": {}}
    html = layout.render("setup_importar_progresso.html", "Importação #4", None,
                         "/setup/importar", imp=imp, percentual=25, parametros=[("amostra", 100)],
                         recarregar=True, ativa=True, aviso=None)
    assert "CAPADMISSION" in html
    assert 'action="/setup/importar/4/cancelar"' in html
    assert 'http-equiv="refresh"' in html
