"""Cadastro de servidores (Setup > Servidores): validacao, secret e tela. Sem banco."""

import pytest

from src import servidores, setup_servidores


def _campos(**mudancas):
    campos = dict(
        tipo="oracle", host="192.168.30.4", porta="", base="IWTST", nome="IW",
        usuario='"nome.sobrenome"', senha_fonte="env", senha_ref="ORACLE_PASSWORD",
        usuario_gcp="DS_IW", senha_fonte_gcp="secret",
        senha_ref_gcp="atlas-iw-oracle-ds-iw-password",
    )
    campos.update(mudancas)
    return servidores._campos(**campos)


def _validar(senha="", criando=True, tinha_cifrada=False, **mudancas):
    servidores.validar(_campos(**mudancas), senha, criando, tinha_cifrada)


def test_os_dois_perfis_do_oracle_do_iw():
    _validar()


def test_perfil_sem_usuario_e_nao_configurado_mas_um_dos_dois_e_obrigatorio():
    _validar(usuario="")
    _validar(usuario_gcp="")
    with pytest.raises(servidores.ConfiguracaoInvalida):
        _validar(usuario="", usuario_gcp="")


def test_secret_e_env_exigem_o_nome_de_onde_vem_a_senha():
    for mudanca in ({"senha_ref": ""}, {"senha_ref_gcp": ""},
                    {"senha_fonte_gcp": "env", "senha_ref_gcp": ""}):
        with pytest.raises(servidores.ConfiguracaoInvalida):
            _validar(**mudanca)


def test_perfil_gcp_nao_aceita_senha_cifrada():
    with pytest.raises(servidores.ConfiguracaoInvalida):
        _validar(senha_fonte_gcp="cifrada", senha="x")
    _validar(senha_fonte_gcp="env", senha_ref_gcp="ORACLE_PASSWORD")


def test_cifrada_exige_senha_so_quando_nao_ha_uma_gravada():
    _validar(senha_fonte="cifrada", senha="s3nha")
    with pytest.raises(servidores.ConfiguracaoInvalida):
        _validar(senha_fonte="cifrada")
    # Editando um servidor que ja tem senha cifrada: em branco mantem a atual
    _validar(senha_fonte="cifrada", criando=False, tinha_cifrada=True)
    # Trocando de env para cifrada sem digitar: nao ha senha para manter
    with pytest.raises(servidores.ConfiguracaoInvalida):
        _validar(senha_fonte="cifrada", criando=False, tinha_cifrada=False)


def test_campos_obrigatorios_e_dominios():
    for campo in ("host", "base", "nome"):
        with pytest.raises(servidores.ConfiguracaoInvalida):
            _validar(**{campo: ""})
    with pytest.raises(servidores.ConfiguracaoInvalida):
        _validar(tipo="sqlite")
    with pytest.raises(servidores.ConfiguracaoInvalida):
        _validar(senha_fonte="texto")


def test_perfil_em_uso_segue_o_ambiente(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("CLOUD_RUN_JOB", raising=False)
    assert servidores.perfil_atual() == "local"
    monkeypatch.setenv("K_SERVICE", "atlas-connect")
    assert servidores.perfil_atual() == "gcp"


def test_cloud_run_job_usa_o_perfil_gcp(monkeypatch):
    # O job de importacao nao tem K_SERVICE, so CLOUD_RUN_JOB
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setenv("CLOUD_RUN_JOB", "atlas-connect-import")
    assert servidores.perfil_atual() == "gcp"


def test_credencial_le_o_perfil_pedido(monkeypatch):
    monkeypatch.setenv("SENHA_TESTE", "abc")
    servidor = {"id": 1, "usuario": "LOCAL", "senha_fonte": "env", "senha_ref": "SENHA_TESTE",
                "usuario_gcp": "", "senha_fonte_gcp": "secret", "senha_ref_gcp": ""}
    assert servidores.credencial(servidor, "local") == ("LOCAL", "abc")
    with pytest.raises(servidores.ConfiguracaoInvalida):
        servidores.credencial(servidor, "gcp")


def test_porta_vazia_usa_a_do_tipo_e_porta_fora_da_faixa_e_recusada():
    assert servidores.porta_valida("", "oracle") == 1521
    assert servidores.porta_valida("", "postgres") == 5432
    assert servidores.porta_valida("1522", "oracle") == 1522
    for ruim in ("0", "70000", "abc"):
        with pytest.raises(servidores.ConfiguracaoInvalida):
            servidores.porta_valida(ruim, "oracle")


def test_nome_curto_do_secret_vira_caminho_completo_no_projeto():
    assert (
        servidores.nome_do_secret("meu-secret", "atlas-dw-hml-511718")
        == "projects/atlas-dw-hml-511718/secrets/meu-secret/versions/latest"
    )
    assert (
        servidores.nome_do_secret("projects/p/secrets/s", "outro")
        == "projects/p/secrets/s/versions/latest"
    )
    assert servidores.nome_do_secret("projects/p/secrets/s/versions/3") == (
        "projects/p/secrets/s/versions/3"
    )
    with pytest.raises(servidores.ConfiguracaoInvalida):
        servidores.nome_do_secret("meu-secret", "")


def test_trocar_para_cifrada_descarta_a_referencia_antiga():
    assert _campos(senha_fonte="cifrada", senha_ref="velho")["senha_ref"] == ""


def test_a_tela_mostra_a_origem_da_senha_nunca_o_valor():
    servidor = {"usuario": "U", "senha_fonte": "cifrada", "senha_final": "x9z1", "senha_ref": "",
                "usuario_gcp": "DS_IW", "senha_fonte_gcp": "secret", "senha_ref_gcp": "atlas-iw"}
    assert setup_servidores.descrever_perfil(servidor, "local") == "U · cifrada ••••x9z1"
    assert setup_servidores.descrever_perfil(servidor, "gcp") == "DS_IW · secret atlas-iw"
    servidor["usuario"] = ""
    assert setup_servidores.descrever_perfil(servidor, "local") == "não configurado"


def test_formulario_novo_renderiza_com_o_passo_a_passo_do_gcp(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "atlas-dw-hml-511718")
    monkeypatch.delenv("K_SERVICE", raising=False)
    html, status = setup_servidores.gerar_form(None)
    assert status == 200
    assert 'name="senha_fonte"' in html and 'name="senha_fonte_gcp"' in html
    # O perfil gcp nao oferece senha cifrada
    gcp = html[html.index('name="senha_fonte_gcp"'):]
    assert 'value="cifrada"' not in gcp[:gcp.index("</select>")]
    assert "em uso neste ambiente" in html
    assert "atlas-app-connect@atlas-dw-hml-511718.iam.gserviceaccount.com" in html
    assert "roles/secretmanager.secretAccessor" in html
    # Sem servidor gravado nao ha o que testar nem excluir
    assert "/testar" not in html
    assert "Excluir servidor" not in html
