"""Servidores de origem cadastrados em Setup > Servidores.

catalogo.servidor -> catalogo.esquema -> catalogo.objeto: e daqui que o
esquema_id de cada objeto diz de onde o dado veio. Este modulo e a regra de
negocio do cadastro (validacao, credencial, teste de conexao); a tela fica em
src/setup_servidores.py.

Cada servidor tem DOIS PERFIS de conexao, porque o mesmo banco e acessado com
credenciais diferentes em cada lugar -- no Oracle do IW, o usuario pessoal com a
senha do .env no local, e DS_IW com o secret do Datastream no Cloud Run. O app
usa o perfil do ambiente em que esta rodando (perfil_atual()).

A senha tem tres fontes (ver o bloco "Credencial do servidor" no DDL):
cifrada no banco, secret do Secret Manager ou variavel de ambiente. Em nenhuma
delas o valor volta para a tela: a cifrada mostra so os quatro ultimos
caracteres, as outras duas so o NOME de onde a senha vem.
"""

import base64
import logging
import os
import time
import urllib.request

from . import catalogo, provedores

logger = logging.getLogger(__name__)

TIPOS = ("oracle", "mssql", "postgres", "mysql")
PORTA_PADRAO = {"oracle": 1521, "mssql": 1433, "postgres": 5432, "mysql": 3306}
ROTULO_FONTE = {
    "env": "Variável de ambiente",
    "cifrada": "Cifrada no banco",
    "secret": "Secret Manager",
}

# Fontes aceitas em cada perfil, na ordem do select. No Cloud Run a senha mora
# no Secret Manager (ou chega por --set-secrets como variavel); cifrada fica so
# no local -- uma coluna cifrada por servidor basta, e na nuvem ela seria um
# segundo lugar para a mesma senha.
PERFIS = {
    "local": {
        "rotulo": "Local",
        "fontes": ("env", "cifrada", "secret"),
        "colunas": ("usuario", "senha_fonte", "senha_ref"),
    },
    "gcp": {
        "rotulo": "GCP (Cloud Run)",
        "fontes": ("secret", "env"),
        "colunas": ("usuario_gcp", "senha_fonte_gcp", "senha_ref_gcp"),
    },
}

# Segundos para o teste de conexao, como o /health: a tela nao pode pendurar.
TIMEOUT = 5
ESCOPO_GCP = "https://www.googleapis.com/auth/cloud-platform"


class ConfiguracaoInvalida(provedores.ConfiguracaoInvalida):
    """Mesmo formato (motivo, detalhe) do erro de provedores: as rotas tratam igual."""


# --------------------------------------------------------------------------
# Ambiente: o que a tela precisa saber para montar o passo a passo do GCP
# --------------------------------------------------------------------------


def no_cloud_run():
    # K_SERVICE e definida pelo proprio Cloud Run em todo container
    return bool(os.getenv("K_SERVICE"))


def projeto_gcp():
    """Projeto para resolver nome curto de secret. Sem o fallback inventado do
    layout.PROJETO: um projeto errado aqui vira 404 do Secret Manager."""
    return os.getenv("PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or ""


_sa_runtime = None


def sa_runtime():
    """E-mail da SA que o Cloud Run usa, pelo metadata server. Vazio fora dele."""
    global _sa_runtime
    if _sa_runtime is not None:
        return _sa_runtime
    _sa_runtime = ""
    if not no_cloud_run():
        return _sa_runtime
    pedido = urllib.request.Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/email",
        headers={"Metadata-Flavor": "Google"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=2) as resposta:
            _sa_runtime = resposta.read().decode().strip()
    except Exception as e:
        logger.warning("metadata server nao devolveu a SA de runtime: %s", e)
    return _sa_runtime


# --------------------------------------------------------------------------
# Secret Manager (REST com google-auth: sem dependencia nova na imagem)
# --------------------------------------------------------------------------


def nome_do_secret(ref, projeto=None):
    """"nome" -> projects/<projeto>/secrets/nome/versions/latest.

    Aceita tambem projects/p/secrets/s e o caminho completo com a versao, para
    secret de outro projeto ou versao fixa.
    """
    ref = (ref or "").strip().strip("/")
    if ref.startswith("projects/"):
        return ref if "/versions/" in ref else f"{ref}/versions/latest"
    projeto = projeto if projeto is not None else projeto_gcp()
    if not projeto:
        raise ConfiguracaoInvalida(
            "Não sabemos em que projeto procurar o secret",
            "Defina PROJECT_ID no ambiente ou informe o caminho completo: "
            "projects/<projeto>/secrets/<nome>.",
        )
    return f"projects/{projeto}/secrets/{ref}/versions/latest"


def ler_secret(ref):
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError
    from google.auth.transport.requests import AuthorizedSession

    nome = nome_do_secret(ref)
    try:
        credenciais, _ = google.auth.default(scopes=[ESCOPO_GCP])
    except DefaultCredentialsError as e:
        raise ConfiguracaoInvalida(
            "Sem credencial do Google para ler o secret",
            "No local, rode gcloud auth application-default login ou use a fonte "
            "'Cifrada no banco'.",
        ) from e

    url = f"https://secretmanager.googleapis.com/v1/{nome}:access"
    try:
        resposta = AuthorizedSession(credenciais).get(url, timeout=TIMEOUT * 2)
    except Exception as e:
        raise ConfiguracaoInvalida("Secret Manager não respondeu", str(e)) from e

    if resposta.status_code == 200:
        dado = resposta.json()["payload"]["data"]
        return base64.b64decode(dado).decode()

    sa = sa_runtime() or "a SA de runtime"
    if resposta.status_code == 403:
        # O Secret Manager devolve 403 tambem quando o secret nao existe e a SA
        # nao pode listar -- docs/infra/licoes-deploy-gcp-atlas.md, "Secrets".
        raise ConfiguracaoInvalida(
            f"Sem permissão para ler {nome}",
            f"Confira se o secret existe e se {sa} tem "
            "roles/secretmanager.secretAccessor nele (passo a passo abaixo).",
        )
    if resposta.status_code == 404:
        raise ConfiguracaoInvalida(
            f"Secret não encontrado: {nome}",
            "Crie o secret ou corrija o nome (passo a passo abaixo).",
        )
    raise ConfiguracaoInvalida(
        f"Secret Manager devolveu HTTP {resposta.status_code}",
        resposta.text[:300],
    )




def perfil_atual():
    return "gcp" if no_cloud_run() else "local"


def perfil_de(servidor, perfil):
    """{usuario, senha_fonte, senha_ref} do perfil, com nomes neutros."""
    usuario, fonte, ref = PERFIS[perfil]["colunas"]
    return {
        "usuario": servidor.get(usuario) or "",
        "senha_fonte": servidor.get(fonte) or "",
        "senha_ref": servidor.get(ref) or "",
    }


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------

COLUNAS = """
s.id, s.tipo, s.host, s.porta, s.base, s.nome, s.ativo,
s.usuario, s.senha_fonte, s.senha_final, s.senha_ref,
s.usuario_gcp, s.senha_fonte_gcp, s.senha_ref_gcp, s.atualizado_em
"""

SQL_LISTAR = f"""
SELECT {COLUNAS},
       (SELECT count(*) FROM catalogo.esquema e WHERE e.servidor_id = s.id) AS n_esquemas,
       (SELECT count(*) FROM catalogo.objeto o
          JOIN catalogo.esquema e ON e.id = o.esquema_id
         WHERE e.servidor_id = s.id) AS n_objetos
  FROM catalogo.servidor s
 ORDER BY s.nome
"""

SQL_UM = f"SELECT {COLUNAS} FROM catalogo.servidor s WHERE s.id = %s"

SQL_ESQUEMAS = """
SELECT e.id, e.nome, e.criado_em,
       (SELECT count(*) FROM catalogo.objeto o WHERE o.esquema_id = e.id) AS n_objetos
  FROM catalogo.esquema e
 WHERE e.servidor_id = %s
 ORDER BY e.nome
"""

SQL_CRIAR = """
INSERT INTO catalogo.servidor
    (tipo, host, porta, base, nome, ativo, usuario, senha_fonte, senha_ref,
     usuario_gcp, senha_fonte_gcp, senha_ref_gcp)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
RETURNING id
"""

SQL_ATUALIZAR = """
UPDATE catalogo.servidor
   SET tipo = %s, host = %s, porta = %s, base = %s, nome = %s, ativo = %s,
       usuario = %s, senha_fonte = %s, senha_ref = %s,
       usuario_gcp = %s, senha_fonte_gcp = %s, senha_ref_gcp = %s,
       atualizado_em = now()
 WHERE id = %s
"""

SQL_TROCAR_SENHA = """
UPDATE catalogo.servidor
   SET senha_cifrada = pgp_sym_encrypt(%s, %s), senha_final = %s,
       atualizado_em = now()
 WHERE id = %s
"""

# Trocar a fonte local para fora de 'cifrada' apaga a senha guardada: nao fica
# segredo esquecido no banco que nenhuma tela mostra.
SQL_LIMPAR_SENHA = """
UPDATE catalogo.servidor SET senha_cifrada = NULL, senha_final = '' WHERE id = %s
"""

SQL_SENHA_CIFRADA = """
SELECT pgp_sym_decrypt(senha_cifrada, %s) AS senha
  FROM catalogo.servidor WHERE id = %s AND senha_cifrada IS NOT NULL
"""

# ON DELETE CASCADE vai de servidor a objeto: excluir um servidor com objetos
# apagaria o catalogo dele, descricoes de IA e vetores incluidos. Por isso o
# DELETE so passa quando nao ha objeto -- a checagem vai no proprio SQL, sem
# janela entre conferir e apagar.
SQL_EXCLUIR = """
DELETE FROM catalogo.servidor s
 WHERE s.id = %s
   AND NOT EXISTS (SELECT 1 FROM catalogo.objeto o
                     JOIN catalogo.esquema e ON e.id = o.esquema_id
                    WHERE e.servidor_id = s.id)
RETURNING id
"""

SQL_CRIAR_ESQUEMA = """
INSERT INTO catalogo.esquema (servidor_id, nome) VALUES (%s, %s)
ON CONFLICT (servidor_id, nome) DO NOTHING
"""

SQL_EXCLUIR_ESQUEMA = """
DELETE FROM catalogo.esquema e
 WHERE e.id = %s AND e.servidor_id = %s
   AND NOT EXISTS (SELECT 1 FROM catalogo.objeto o WHERE o.esquema_id = e.id)
RETURNING id
"""


def listar():
    return catalogo.consultar(SQL_LISTAR, (), "servidores cadastrados")


def buscar(servidor_id):
    return catalogo.um(SQL_UM, (servidor_id,), f"servidor {servidor_id}")


def esquemas(servidor_id):
    return catalogo.consultar(SQL_ESQUEMAS, (servidor_id,), f"esquemas do servidor {servidor_id}")


def porta_valida(texto, tipo):
    texto = (str(texto) if texto is not None else "").strip()
    if not texto:
        return PORTA_PADRAO.get(tipo, 0)
    try:
        porta = int(texto)
    except ValueError:
        porta = 0
    if not 0 < porta < 65536:
        raise ConfiguracaoInvalida("Porta inválida", "Use um número entre 1 e 65535.")
    return porta


def validar_perfil(perfil, usuario, senha_fonte, senha_ref, senha="", criando=True,
                   tinha_cifrada=False):
    """Usuario vazio = perfil nao configurado, e passa. Preenchido, tem de fechar."""
    rotulo = PERFIS[perfil]["rotulo"]
    if not usuario:
        return
    if senha_fonte not in PERFIS[perfil]["fontes"]:
        aceitas = ", ".join(ROTULO_FONTE[f] for f in PERFIS[perfil]["fontes"])
        raise ConfiguracaoInvalida(f"Perfil {rotulo}: a senha vem de {aceitas}")
    if senha_fonte in ("secret", "env") and not senha_ref:
        raise ConfiguracaoInvalida(
            f"Perfil {rotulo}: informe de onde vem a senha",
            "O nome do secret no Secret Manager."
            if senha_fonte == "secret"
            else "O nome da variável de ambiente (ex.: ORACLE_PASSWORD).",
        )
    # Editar sem digitar a senha mantem a atual -- mas so se ja havia uma
    if senha_fonte == "cifrada" and not senha and (criando or not tinha_cifrada):
        raise ConfiguracaoInvalida(
            f"Perfil {rotulo}: digite a senha", "Ela é cifrada antes de ir para o banco."
        )


def validar(c, senha, criando, tinha_cifrada=False):
    faltando = [
        rotulo
        for rotulo, chave in (("nome", "nome"), ("host", "host"), ("base", "base"))
        if not c[chave]
    ]
    if faltando:
        raise ConfiguracaoInvalida(f"Preencha: {', '.join(faltando)}")
    if c["tipo"] not in TIPOS:
        raise ConfiguracaoInvalida(f"Tipo precisa ser um de {', '.join(TIPOS)}")
    if not c["usuario"] and not c["usuario_gcp"]:
        raise ConfiguracaoInvalida(
            "Configure ao menos um perfil de conexão",
            "Preencha o usuário do perfil Local, do GCP ou dos dois.",
        )
    validar_perfil("local", c["usuario"], c["senha_fonte"], c["senha_ref"], senha,
                   criando, tinha_cifrada)
    validar_perfil("gcp", c["usuario_gcp"], c["senha_fonte_gcp"], c["senha_ref_gcp"])


def _campos(tipo, host, porta, base, nome, usuario, senha_fonte, senha_ref,
            usuario_gcp, senha_fonte_gcp, senha_ref_gcp):
    tipo = (tipo or "").strip()
    senha_fonte = (senha_fonte or "env").strip()
    return dict(
        tipo=tipo,
        host=(host or "").strip(),
        porta=porta_valida(porta, tipo),
        base=(base or "").strip(),
        nome=(nome or "").strip(),
        usuario=(usuario or "").strip(),
        senha_fonte=senha_fonte,
        # A fonte cifrada nao usa referencia: limpa para nao exibir lixo antigo
        senha_ref="" if senha_fonte == "cifrada" else (senha_ref or "").strip(),
        usuario_gcp=(usuario_gcp or "").strip(),
        senha_fonte_gcp=(senha_fonte_gcp or "secret").strip(),
        senha_ref_gcp=(senha_ref_gcp or "").strip(),
    )


def _valores_sql(c):
    return (c["tipo"], c["host"], c["porta"], c["base"], c["nome"], c["ativo"],
            c["usuario"], c["senha_fonte"], c["senha_ref"],
            c["usuario_gcp"], c["senha_fonte_gcp"], c["senha_ref_gcp"])


def _duplicado(falha):
    if "servidor_tipo_host_porta_base_key" in str(falha.causa):
        return ConfiguracaoInvalida(
            "Já existe um servidor com esse tipo, host, porta e base",
            "É a chave natural do cadastro: edite o existente.",
        )
    return falha


def criar(ativo, senha, **campos):
    c = _campos(**campos)
    c["ativo"] = ativo
    validar(c, senha, criando=True)
    cifrar = c["usuario"] and c["senha_fonte"] == "cifrada"
    # A senha mestra e conferida antes do INSERT: sem ela o servidor ficaria
    # gravado sem a senha que o usuario acabou de digitar.
    mestra = provedores.senha_mestra() if cifrar else None
    try:
        linha = catalogo.um(SQL_CRIAR, _valores_sql(c), f"criação do servidor {c['nome']}")
    except catalogo.ConsultaFalhou as falha:
        raise _duplicado(falha) from falha
    servidor_id = linha["id"]
    if mestra:
        catalogo.executar(
            SQL_TROCAR_SENHA, (senha, mestra, senha[-4:], servidor_id),
            f"senha do servidor {servidor_id}",
        )
    return servidor_id


def atualizar(servidor_id, ativo, senha, **campos):
    """Senha em branco com a fonte local 'cifrada' mantem a atual."""
    atual = buscar(servidor_id)
    if not atual:
        raise ConfiguracaoInvalida("Servidor não encontrado")
    c = _campos(**campos)
    c["ativo"] = ativo
    validar(c, senha, criando=False,
            tinha_cifrada=atual["senha_fonte"] == "cifrada" and bool(atual["senha_final"]))
    usa_cifrada = c["usuario"] and c["senha_fonte"] == "cifrada"
    mestra = provedores.senha_mestra() if usa_cifrada and senha else None
    try:
        catalogo.executar(
            SQL_ATUALIZAR, _valores_sql(c) + (servidor_id,),
            f"atualização do servidor {servidor_id}",
        )
    except catalogo.ConsultaFalhou as falha:
        raise _duplicado(falha) from falha
    if mestra:
        catalogo.executar(
            SQL_TROCAR_SENHA, (senha, mestra, senha[-4:], servidor_id),
            f"troca de senha do servidor {servidor_id}",
        )
    elif not usa_cifrada:
        catalogo.executar(SQL_LIMPAR_SENHA, (servidor_id,), f"limpeza da senha do servidor {servidor_id}")


def excluir(servidor_id):
    apagado = catalogo.um(SQL_EXCLUIR, (servidor_id,), f"exclusão do servidor {servidor_id}")
    if not apagado:
        raise ConfiguracaoInvalida(
            "O servidor tem objetos no catálogo",
            "Excluir apagaria o catálogo dele, com descrições e vetores. Desative-o em vez disso.",
        )


def criar_esquema(servidor_id, nome):
    nome = (nome or "").strip()
    if not nome:
        raise ConfiguracaoInvalida("Informe o nome do schema")
    catalogo.executar(SQL_CRIAR_ESQUEMA, (servidor_id, nome), f"schema {nome} do servidor {servidor_id}")


def excluir_esquema(servidor_id, esquema_id):
    apagado = catalogo.um(
        SQL_EXCLUIR_ESQUEMA, (esquema_id, servidor_id), f"exclusão do schema {esquema_id}"
    )
    if not apagado:
        raise ConfiguracaoInvalida(
            "O schema tem objetos no catálogo",
            "Excluir apagaria o catálogo dele, com descrições e vetores.",
        )


# --------------------------------------------------------------------------
# Credencial e teste de conexao
# --------------------------------------------------------------------------


def senha_de(servidor, perfil):
    """A senha em claro, da fonte do perfil. So para conectar; nunca vai a tela."""
    p = perfil_de(servidor, perfil)
    fonte, ref = p["senha_fonte"], p["senha_ref"]
    if fonte == "secret":
        return ler_secret(ref)
    if fonte == "env":
        senha = os.getenv(ref)
        if not senha:
            raise ConfiguracaoInvalida(
                f"Variável {ref or '(sem nome)'} vazia neste ambiente",
                "Confira o .env (local) ou o --set-secrets do deploy (GCP).",
            )
        return senha
    try:
        linha = catalogo.um(
            SQL_SENHA_CIFRADA, (provedores.senha_mestra(), servidor["id"]),
            f"senha do servidor {servidor['id']}",
        )
    except catalogo.ConsultaFalhou as falha:
        if "Wrong key" in str(falha.causa) or "corrupt data" in str(falha.causa):
            raise ConfiguracaoInvalida(
                "Não conseguimos decifrar a senha",
                "A IA_SENHA_MESTRA deste ambiente não é a que cifrou a senha. Digite-a de novo.",
            ) from falha
        raise
    if not linha:
        raise ConfiguracaoInvalida("Nenhuma senha gravada", "Edite o servidor e digite a senha.")
    return linha["senha"]


def credencial(servidor, perfil=None):
    """(usuario, senha) do perfil -- por padrao, o do ambiente em que o app roda.

    E a porta de entrada para quem for conectar na origem (o teste da tela hoje;
    o mapeador e o /health quando passarem a ler o cadastro).
    """
    perfil = perfil or perfil_atual()
    usuario = perfil_de(servidor, perfil)["usuario"]
    if not usuario:
        raise ConfiguracaoInvalida(
            f"Perfil {PERFIS[perfil]['rotulo']} não configurado",
            "Preencha o usuário e a origem da senha desse perfil e grave.",
        )
    return usuario, senha_de(servidor, perfil)


def testar(servidor_id, perfil=None):
    """(ok, mensagem, ms). Mesma pergunta do /health: SELECT USER FROM dual."""
    servidor = buscar(servidor_id)
    if not servidor:
        raise ConfiguracaoInvalida("Servidor não encontrado")
    perfil = perfil or perfil_atual()
    rotulo = PERFIS[perfil]["rotulo"]
    if servidor["tipo"] != "oracle":
        return False, f"O teste ainda só conhece Oracle; este servidor é {servidor['tipo']}.", None

    try:
        usuario, senha = credencial(servidor, perfil)
    except ConfiguracaoInvalida as e:
        return False, f"Perfil {rotulo}: {e.motivo}. {e.detalhe}".strip(), None

    import oracledb

    destino = f"{servidor['host']}:{servidor['porta']}/{servidor['base']}"
    inicio = time.perf_counter()
    conexao = None
    try:
        conexao = oracledb.connect(
            user=usuario, password=senha, dsn=destino, tcp_connect_timeout=TIMEOUT,
        )
        conexao.call_timeout = TIMEOUT * 1000
        with conexao.cursor() as cursor:
            cursor.execute("SELECT USER FROM dual")
            usuario_sessao = cursor.fetchone()[0]
    except Exception as e:
        ms = (time.perf_counter() - inicio) * 1000
        logger.error("servidor %s (%s, perfil %s) nao respondeu: %s", servidor_id, destino, perfil, e)
        return False, f"Perfil {rotulo}: {str(e).strip().splitlines()[0]}", ms
    finally:
        if conexao is not None:
            conexao.close()
    ms = (time.perf_counter() - inicio) * 1000
    return True, f"Perfil {rotulo}: conectado em {destino} como {usuario_sessao}.", ms
