"""Importacao do schema de origem disparada por Setup > Importar dados.

Quem importa e o mesmo scripts/mapear_oracle.py do `make catalogo`, chamado com
--importacao N (a linha de catalogo.importacao que recebe o progresso) e
--esquema-id N (origem e credencial do cadastro de Setup > Servidores).

Onde ele roda depende do ambiente:
- no Cloud Run, num Cloud Run Job (IMPORT_JOB), com a mesma imagem, VPC e
  secrets do servico. O mapeamento completo leva horas, e o servico, com
  min-instances=0, pode ser desligado no meio -- o job nao;
- no local, num processo destacado, como o lote de IA (src/lote.py).

O cancelamento e cooperativo: a tela marca a linha como cancelada e o mapeador,
que confere a linha a cada objeto, para no proximo. Na nuvem a execucao tambem
recebe o cancel do Cloud Run, para nao esperar uma query longa terminar.
"""

import json
import logging
import os
import subprocess
import sys

from . import catalogo, servidores

logger = logging.getLogger(__name__)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = "scripts/mapear_oracle.py"

MODOS = {
    "completo": "Mapeamento completo",
    "amostras": "Só amostras",
}

# Sem batimento ha mais que isto, a execucao morreu sem fechar a linha (job
# derrubado, container reciclado). O mapeador bate a cada objeto, e cada query no
# Oracle tem no maximo TIMEOUT_MAXIMO segundos, entao 20 min de folga sobra.
MINUTOS_SEM_SINAL = 20
TIMEOUT_MAXIMO = 600
ESCOPO_GCP = "https://www.googleapis.com/auth/cloud-platform"


class ImportacaoInvalida(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


# --------------------------------------------------------------------------
# Ambiente
# --------------------------------------------------------------------------


def job():
    return os.getenv("IMPORT_JOB", "").strip()


def regiao():
    return os.getenv("REGION", "").strip()


def disponivel():
    """(pode disparar, por que nao). No local sempre pode; no Cloud Run, so com o job."""
    if not servidores.no_cloud_run():
        return True, ""
    faltando = [nome for nome, valor in (
        ("IMPORT_JOB", job()), ("REGION", regiao()), ("PROJECT_ID", servidores.projeto_gcp()),
    ) if not valor]
    if faltando:
        return False, (
            "Este ambiente não tem o Cloud Run Job de importação "
            f"(faltam {', '.join(faltando)} no deploy). Em prd não há VPN para o Oracle."
        )
    return True, ""


def onde_roda():
    if servidores.no_cloud_run():
        return f"Cloud Run Job {job() or '(não configurado)'}"
    return "processo local destacado"


# --------------------------------------------------------------------------
# Parametros
# --------------------------------------------------------------------------


def _inteiro(texto, rotulo, minimo, maximo=None):
    texto = (str(texto) if texto is not None else "").strip()
    if not texto:
        return None
    try:
        valor = int(texto)
    except ValueError as e:
        raise ImportacaoInvalida(f"{rotulo} precisa ser um número inteiro") from e
    if valor < minimo or (maximo is not None and valor > maximo):
        faixa = f"entre {minimo} e {maximo}" if maximo is not None else f"a partir de {minimo}"
        raise ImportacaoInvalida(f"{rotulo} precisa estar {faixa}")
    return valor


def parametros_do_form(dados):
    """Formulario -> (modo, parametros validados). As regras sao as do script."""
    modo = (dados.get("modo") or "").strip()
    if modo not in MODOS:
        raise ImportacaoInvalida("Escolha o que importar")

    amostra = _inteiro(dados.get("amostra"), "Linhas de amostra", 0, 1000)
    parametros = {
        "tabelas": (dados.get("tabelas") or "").strip() or None,
        "limite": _inteiro(dados.get("limite"), "Limite de objetos", 1),
        "amostra": 100 if amostra is None else amostra,
        "timeout": _inteiro(dados.get("timeout"), "Timeout por query", 5, TIMEOUT_MAXIMO) or 60,
        "contagem_exata": bool(dados.get("contagem_exata")),
        "sem_views": bool(dados.get("sem_views")),
        "pular_existentes": bool(dados.get("pular_existentes")),
    }

    if modo == "amostras":
        if parametros["amostra"] <= 0:
            raise ImportacaoInvalida(
                "Só amostras com 0 linhas apagaria as amostras",
                "Informe quantas linhas trazer por objeto.",
            )
        if parametros["pular_existentes"]:
            raise ImportacaoInvalida(
                "“Pular existentes” não combina com “Só amostras”",
                "Ele pula o que já está no catálogo, e neste modo isso é o schema "
                "inteiro: a importação passaria por todos sem fazer nada.",
            )
    return modo, parametros


def argumentos(importacao):
    """Argumentos do mapeador para uma linha de catalogo.importacao."""
    p = importacao["parametros"]
    args = [
        "--importacao", str(int(importacao["id"])),
        "--esquema-id", str(int(importacao["esquema_id"])),
        "--amostra", str(int(p.get("amostra", 100))),
        "--timeout", str(int(p.get("timeout", 60))),
    ]
    if importacao["modo"] == "amostras":
        args.append("--somente-amostras")
    if p.get("tabelas"):
        args += ["--tabelas", p["tabelas"]]
    if p.get("limite"):
        args += ["--limite", str(int(p["limite"]))]
    for chave, opcao in (("contagem_exata", "--contagem-exata"), ("sem_views", "--sem-views"),
                         ("pular_existentes", "--pular-existentes")):
        if p.get(chave):
            args.append(opcao)
    return args


# --------------------------------------------------------------------------
# Banco
# --------------------------------------------------------------------------

COLUNAS = """
i.id, i.esquema_id, i.modo, i.parametros, i.status, i.solicitada_por, i.solicitada_em,
i.iniciada_em, i.heartbeat_em, i.concluida_em, i.total, i.processados, i.objeto_atual,
i.erros, i.execucao, e.nome AS esquema, s.nome AS servidor
"""
ORIGEM = """
catalogo.importacao i
JOIN catalogo.esquema e ON e.id = i.esquema_id
JOIN catalogo.servidor s ON s.id = e.servidor_id
"""

SQL_SEM_SINAL = f"""
UPDATE catalogo.importacao
   SET status = 'falhou', concluida_em = now(), objeto_atual = NULL,
       erros = erros || jsonb_build_array(
           'sem sinal da execucao ha mais de {MINUTOS_SEM_SINAL} min -- ela parou sem '
           'fechar. Rode de novo com "pular existentes" para retomar.')
 WHERE status IN ('pendente', 'rodando')
   AND coalesce(heartbeat_em, solicitada_em) < now() - interval '{MINUTOS_SEM_SINAL} minutes'
"""


def marcar_sem_sinal():
    """Fecha a execucao que morreu sem avisar; senao ela travaria a proxima."""
    catalogo.executar(SQL_SEM_SINAL, (), "importacoes sem sinal")


def em_andamento():
    return catalogo.um(
        f"SELECT {COLUNAS} FROM {ORIGEM} WHERE i.status IN ('pendente', 'rodando') LIMIT 1",
        (), "importacao em andamento",
    )


def listar():
    return catalogo.consultar(
        f"SELECT {COLUNAS} FROM {ORIGEM} ORDER BY i.id DESC LIMIT 20", (), "importacoes",
    )


def buscar(importacao_id):
    return catalogo.um(
        f"SELECT {COLUNAS} FROM {ORIGEM} WHERE i.id = %s", (importacao_id,),
        f"importacao {importacao_id}",
    )


def esquemas_oracle():
    """Schemas que o mapeador sabe importar: os dos servidores Oracle ativos."""
    return catalogo.consultar(
        """SELECT e.id, e.nome, s.nome AS servidor
             FROM catalogo.esquema e JOIN catalogo.servidor s ON s.id = e.servidor_id
            WHERE s.tipo = 'oracle' AND s.ativo
            ORDER BY s.nome, e.nome""",
        (), "schemas importaveis",
    )


def _esquema(esquema_id):
    linha = catalogo.um(
        """SELECT e.id, e.nome, e.servidor_id, s.tipo, s.ativo
             FROM catalogo.esquema e JOIN catalogo.servidor s ON s.id = e.servidor_id
            WHERE e.id = %s""",
        (esquema_id,), f"schema {esquema_id}",
    )
    if not linha:
        raise ImportacaoInvalida("Schema não encontrado", "Escolha um schema da lista.")
    if linha["tipo"] != "oracle":
        raise ImportacaoInvalida("O mapeador só conhece Oracle")
    if not linha["ativo"]:
        raise ImportacaoInvalida("O servidor deste schema está inativo")
    return linha


def criar(esquema_id, modo, parametros, usuario=None):
    _esquema(esquema_id)
    marcar_sem_sinal()
    aberta = em_andamento()
    if aberta:
        raise ImportacaoInvalida(
            f"A importação #{aberta['id']} ainda está em andamento",
            "Espere terminar ou cancele: duas escrevendo no mesmo catálogo se atropelam.",
        )
    try:
        linha = catalogo.um(
            """INSERT INTO catalogo.importacao (esquema_id, modo, parametros, solicitada_por)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (esquema_id, modo, json.dumps(parametros), usuario),
            "criacao da importacao",
        )
    except catalogo.ConsultaFalhou as falha:
        # O indice unico parcial pegou dois cliques quase juntos
        if "importacao_uma_ativa_idx" in str(falha.causa):
            raise ImportacaoInvalida("Já há uma importação em andamento") from falha
        raise
    logger.info("importacao %s (%s) criada para o schema %s", linha["id"], modo, esquema_id)
    return linha["id"]


def _fechar(importacao_id, status, erro):
    catalogo.executar(
        """UPDATE catalogo.importacao
              SET status = %s, concluida_em = now(), objeto_atual = NULL,
                  erros = erros || jsonb_build_array(%s::text)
            WHERE id = %s AND status IN ('pendente', 'rodando')""",
        (status, erro, importacao_id),
        f"fechamento da importacao {importacao_id}",
    )


# --------------------------------------------------------------------------
# Disparo e cancelamento
# --------------------------------------------------------------------------


def _sessao():
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credenciais, _ = google.auth.default(scopes=[ESCOPO_GCP])
    return AuthorizedSession(credenciais)


def url_do_job():
    return (
        f"https://run.googleapis.com/v2/projects/{servidores.projeto_gcp()}"
        f"/locations/{regiao()}/jobs/{job()}"
    )


def corpo_do_run(args):
    """Override do container: o job sobe com `python scripts/mapear_oracle.py`, e o
    override de args SUBSTITUI os do job, entao o script vai de novo na frente."""
    return {
        "overrides": {
            "containerOverrides": [{"args": [SCRIPT, *args]}],
            "taskCount": 1,
        }
    }


def _disparar_job(args):
    resposta = _sessao().post(f"{url_do_job()}:run", json=corpo_do_run(args), timeout=30)
    if resposta.status_code == 403:
        raise ImportacaoInvalida(
            "Sem permissão para executar o job de importação",
            f"A SA de runtime ({servidores.sa_runtime() or 'do serviço'}) precisa de "
            f"roles/run.developer no job {job()} (docs/gcp-setup.md, seção 10).",
        )
    if resposta.status_code == 404:
        raise ImportacaoInvalida(
            f"Job {job()} não encontrado em {regiao()}",
            "Confira o passo do job no workflow de deploy.",
        )
    if resposta.status_code >= 300:
        raise ImportacaoInvalida(
            f"O Cloud Run devolveu HTTP {resposta.status_code}", resposta.text[:300],
        )
    # Long-running operation; o metadata e a Execution, cujo name e o que cancela
    operacao = resposta.json()
    return (operacao.get("metadata") or {}).get("name") or operacao.get("name", "")


def _disparar_local(args):
    processo = subprocess.Popen(  # noqa: S603 - argumentos montados por argumentos()
        [sys.executable, os.path.join(RAIZ, SCRIPT), *args],
        cwd=RAIZ,
        start_new_session=True,
        # Herda stdout/stderr: o log do mapeador sai junto com o do app
    )
    return f"pid:{processo.pid}"


def disparar(importacao_id):
    importacao = buscar(importacao_id)
    args = argumentos(importacao)
    try:
        if servidores.no_cloud_run():
            pronto, motivo = disponivel()
            if not pronto:
                raise ImportacaoInvalida("Importação indisponível neste ambiente", motivo)
            execucao = _disparar_job(args)
        else:
            execucao = _disparar_local(args)
    except ImportacaoInvalida as falha:
        _fechar(importacao_id, "falhou", f"{falha.motivo}. {falha.detalhe}".strip())
        raise
    except Exception as e:
        _fechar(importacao_id, "falhou", f"disparo: {e}")
        raise ImportacaoInvalida("Não conseguimos disparar a importação", str(e)) from e

    catalogo.executar(
        "UPDATE catalogo.importacao SET execucao = %s WHERE id = %s",
        (execucao, importacao_id), f"execucao da importacao {importacao_id}",
    )
    logger.info("importacao %s disparada: %s", importacao_id, execucao)
    return execucao


def cancelar(importacao_id, usuario=None):
    importacao = buscar(importacao_id)
    if not importacao:
        return
    quem = f" por {usuario}" if usuario else ""
    _fechar(importacao_id, "cancelada", f"cancelada na tela{quem}")

    # Na nuvem, alem do cooperativo, para a execucao: uma amostra ou contagem
    # longa no Oracle demoraria para chegar no proximo objeto.
    execucao = importacao.get("execucao") or ""
    if execucao.startswith("projects/") and servidores.no_cloud_run():
        try:
            resposta = _sessao().post(
                f"https://run.googleapis.com/v2/{execucao}:cancel", json={}, timeout=30
            )
            if resposta.status_code >= 300:
                logger.warning("cancel da execucao %s devolveu HTTP %s: %s", execucao,
                               resposta.status_code, resposta.text[:300])
        except Exception as e:  # noqa: BLE001 - o cooperativo ja foi gravado
            logger.warning("cancel da execucao %s falhou: %s", execucao, e)


# --------------------------------------------------------------------------
# Acoes imediatas (sem job)
# --------------------------------------------------------------------------


def testar_conexao(esquema_id):
    """(ok, mensagem, ms) do servidor do schema, no perfil deste ambiente."""
    return servidores.testar(_esquema(esquema_id)["servidor_id"])


def aplicar_ddl():
    return catalogo.aplicar_ddl()


def percentual(importacao):
    total = importacao.get("total") or 0
    if not total:
        return 100 if importacao["status"] == "concluida" else 0
    return min(100, round((importacao.get("processados") or 0) * 100 / total))
