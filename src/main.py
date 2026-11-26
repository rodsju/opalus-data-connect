
import contextlib
import os
import threading
import urllib.parse

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import layout
from . import lote as lote_mod
from . import log as log_mod
from . import api as api_mod
from . import catalogo as catalogo_mod
from . import comparacao as comparacao_mod
from . import comparar as comparar_view
from . import config as config_mod
from . import consulta as consulta_mod
from . import consulta_view
from . import debug as debug_view
from . import embeddings as embeddings_mod
from . import esquemas as esquemas_mod
from . import grafo as grafo_mod
from . import health as health_view
from . import home as home_view
from . import importacao as importacao_mod
from . import ia as ia_view
from . import oracle as oracle_view
from . import provedores as provedores_mod
from . import servidores as servidores_mod
from . import setup as setup_view
from . import setup_importar as setup_importar_view
from . import setup_lote as setup_lote_view
from . import setup_servidores as setup_servidores_view
from . import usuario as usuario_mod

# Antes de qualquer rota: sem isto os logger.error dos modulos nao saem formatados
log_mod.configurar()


@contextlib.asynccontextmanager
async def ciclo_de_vida(_app):
    """Migra o catalogo no boot, em segundo plano. DDL_NO_BOOT=1 desliga (ex.: um
    banco onde o app nao e o dono do schema).

    Em segundo plano porque as tentativas podem levar minutos (a rede da VPC
    demora a ficar pronta no Cloud Run, catalogo.aplicar_ddl_no_boot) e o
    container precisa escutar a porta antes disso.
    """
    # Thread daemon, nao asyncio.to_thread: o executor padrao seria esperado no
    # shutdown, e um SIGTERM no meio das tentativas seguraria o container.
    if os.getenv("DDL_NO_BOOT", "").strip().lower() not in ("1", "true", "sim"):
        threading.Thread(
            target=catalogo_mod.aplicar_ddl_no_boot, name="ddl-boot", daemon=True
        ).start()
    yield


app = FastAPI(lifespan=ciclo_de_vida)

# Ativos da aplicação (src/static)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Design system Opalus servido a partir da raiz do projeto
DS_DIR = os.path.join(BASE_DIR, "..", "ds_opalus")
app.mount("/ds-static", StaticFiles(directory=DS_DIR), name="ds-static")

# Caminhos que nao leem o catalogo: nao pagam a consulta dos schemas. /health
# sobretudo -- a sonda de liveness nao pode depender do Postgres.
SEM_ESQUEMA = ("/static/", "/ds-static/", "/health", "/logout", "/api/")


@app.middleware("http")
async def esquema_do_request(request: Request, chamar):
    """Fixa o schema em uso (pre-filtro de todas as telas) uma vez por request.

    O ContextVar setado aqui chega as rotas sync: o Starlette copia o contexto
    para a thread que as executa. Ver src/esquemas.py.
    """
    if not request.url.path.startswith(SEM_ESQUEMA):
        esquemas_mod.resolver(request.cookies.get(esquemas_mod.COOKIE))
    return await chamar(request)


@app.get("/esquema")
def trocar_esquema(
    id: int = Query(...),
    voltar: str = Query(default="/oracle"),
    objeto: str = Query(default=""),
):
    """Troca o schema em uso e volta para a pagina em que o usuario estava.

    `objeto` abre o detalhe dele no schema novo. O voltar nunca leva a um objeto
    (destino_seguro); quem passa `objeto` -- a comparacao -- sabe que ele existe la.
    """
    destino = esquemas_mod.destino_seguro(voltar)
    if objeto.strip():
        destino = "/oracle/objetos/" + urllib.parse.quote(objeto.strip(), safe="")
    resposta = RedirectResponse(url=destino, status_code=303)
    if any(e["id"] == id for e in esquemas_mod.lista_atual()):
        resposta.set_cookie(
            esquemas_mod.COOKIE, str(id), max_age=esquemas_mod.COOKIE_MAX_AGE,
            path="/", samesite="lax", httponly=True,
        )
    return resposta


def quer_html(request):
    """Navegador recebe pagina; sonda e curl continuam recebendo JSON."""
    return "text/html" in request.headers.get("accept", "")


@app.get("/health")
def health(request: Request):
    if not quer_html(request):
        return JSONResponse(health_view.PAYLOAD)
    html, status = health_view.gerar_pagina(usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.get("/")
def home(request: Request):
    if not quer_html(request):
        return JSONResponse(home_view.PAYLOAD)
    html, status = home_view.gerar_pagina(usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.get("/debug")
def debug(request: Request):
    if not quer_html(request):
        return JSONResponse({"headers": dict(request.headers)})
    html, status = debug_view.gerar_pagina(request, usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.get("/logout")
def logout(request: Request):
    """Expira os cookies desta origem e manda o usuario para o SSO do ambiente."""
    resposta = RedirectResponse(url=layout.SSO_URL, status_code=303)
    for nome in request.cookies:
        # Sem HttpOnly nao daria para limpar cookie de sessao pelo JS
        resposta.delete_cookie(nome, path="/")
    return resposta


@app.get("/oracle")
def oracle(request: Request):
    """Visao geral da ultima extracao do schema Oracle."""
    html, status = oracle_view.gerar_visao_geral(usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.get("/oracle/grafo")
def oracle_grafo(request: Request):
    """Visao Grafo. Registrada ANTES de /oracle/{secao}, senao o path param captura."""
    html, status = oracle_view.gerar_grafo(usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.get("/oracle/grafo.json")
def oracle_grafo_json():
    """Nos e arestas do recorte inteiro; o cliente expande a partir daqui."""
    try:
        return JSONResponse(grafo_mod.grafo_completo(esquemas_mod.atual_id()))
    except catalogo_mod.ConsultaFalhou as falha:
        return JSONResponse({"erro": str(falha.causa)}, status_code=502)


@app.get("/oracle/mapa")
def oracle_mapa(
    request: Request,
    excluir: str = Query(default=""),
    q: str = Query(default=""),
    topk: int = Query(default=oracle_view.TOPK_MAPA, ge=1, le=200),
):
    """Mapa semantico. Registrada ANTES de /oracle/{secao}, senao o path param captura."""
    html, status = oracle_view.gerar_mapa(
        excluir.strip(), q.strip(), topk, usuario_mod.identificar(request)
    )
    return HTMLResponse(content=html, status_code=status)


@app.get("/oracle/mapa.json")
def oracle_mapa_json(
    excluir: str = Query(default=""),
    q: str = Query(default=""),
    topk: int = Query(default=oracle_view.TOPK_MAPA, ge=1, le=200),
    provedor: str = Query(default=""),
):
    """Nos, arestas e duplicatas do recorte.

    COM `q` faz uma chamada paga de embedding, dentro da busca semantica; sem
    `q`, nenhuma. E um GET, entao um F5 com termo repete a chamada -- mesma
    propriedade da tela de busca.
    """
    try:
        return JSONResponse(
            oracle_view.dados_do_mapa(excluir.strip(), q.strip(), topk, provedor or None)
        )
    except catalogo_mod.ConsultaFalhou as falha:
        return JSONResponse({"erro": str(falha.causa)}, status_code=502)
    except (ia_view.GeracaoFalhou, embeddings_mod.EmbutirFalhou,
            provedores_mod.ConfiguracaoInvalida) as falha:
        return JSONResponse({"erro": f"{falha.motivo}. {falha.detalhe}"}, status_code=502)


@app.get("/oracle/busca")
def oracle_busca(
    request: Request,
    q: str = Query(default=""),
    escopo: str = Query(default="ambos"),
    topk: int = Query(default=20, ge=1, le=200),
    provedor: str = Query(default=""),
    excluir: str = Query(default=""),
):
    """Busca semantica. Registrada ANTES de /oracle/{secao}, senao o path param captura.

    GET de proposito: e leitura e a URL fica compartilhavel. A guarda contra o F5
    caro esta em gerar_busca -- termo vazio nao chama a API.
    """
    html, status = oracle_view.gerar_busca(
        q.strip(), escopo, topk, provedor or None, excluir.strip(),
        usuario_mod.identificar(request),
    )
    return HTMLResponse(content=html, status_code=status)


def _filtros_da_lista(dados):
    """Querystring -> {chave interna: valor escolhido}.

    Lido da querystring em vez de um parametro por filtro: assim oracle.FILTROS
    continua sendo a unica lista a mexer quando entrar um filtro novo. Mesmo
    padrao de _filtros_do_lote. Quem valida o valor e oracle.montar_recorte.
    """
    return {
        chave: (dados.get(param) or "").strip()
        for chave, param, _, _ in oracle_view.FILTROS
        if dados.get(param)
    }


# --------------------------------------------------------------------------
# Oracle > Comparar
#
# Antes de /oracle/{secao}: senao "comparar" cairia na rota generica como secao.
# --------------------------------------------------------------------------


@app.get("/oracle/comparar")
def oracle_comparar(
    request: Request,
    nome: str = Query(default=""),
    q: str = Query(default=""),
):
    """Seletor: mesma tabela entre schemas, busca livre e historico."""
    selecionados = []
    for valor in request.query_params.getlist("sel"):
        try:
            selecionados.append(int(valor))
        except ValueError:
            continue
    html, status = comparar_view.gerar_selecao(
        nome, q, selecionados, usuario_mod.identificar(request)
    )
    return HTMLResponse(content=html, status_code=status)


@app.get("/oracle/comparar/ver")
def oracle_comparar_ver(request: Request):
    """Resultado. Aceita ?ids=1,2,3 (link do historico) ou ?sel=1&sel=2 (o form)."""
    usuario = usuario_mod.identificar(request)
    valores = request.query_params.getlist("ids") + request.query_params.getlist("sel")
    try:
        ids = comparacao_mod.ids_validos(valores)
    except comparacao_mod.ComparacaoInvalida as falha:
        html, _ = comparar_view.gerar_selecao(
            selecionados=[int(v) for v in valores if v.isdigit()], usuario=usuario,
            aviso=_aviso_de(falha),
        )
        return HTMLResponse(content=html, status_code=400)
    html, status = comparar_view.gerar_resultado(ids, usuario)
    return HTMLResponse(content=html, status_code=status)


@app.post("/oracle/comparar/gerar")
def oracle_comparar_gerar(
    request: Request, ids: str = Form(default=""), provedor: str = Form(default="")
):
    """Gera a analise por IA, grava e volta. O 303 evita outra chamada paga no F5."""
    usuario = usuario_mod.identificar(request)
    try:
        lista = comparacao_mod.ids_validos(ids)
        objetos = comparacao_mod.carregar(lista)
        analise, meta = comparacao_mod.gerar(
            objetos, comparacao_mod.diferenca(objetos), provedor or None
        )
        comparacao_mod.gravar(objetos, analise, meta, usuario["email"] if usuario else None)
    except (
        comparacao_mod.ComparacaoInvalida,
        ia_view.GeracaoFalhou,
        provedores_mod.ConfiguracaoInvalida,
        catalogo_mod.ConsultaFalhou,
    ) as falha:
        aviso = _aviso_de(falha)
        try:
            html, _ = comparar_view.gerar_resultado(
                comparacao_mod.ids_validos(ids), usuario, aviso
            )
        except comparacao_mod.ComparacaoInvalida:
            html, _ = comparar_view.gerar_selecao(usuario=usuario, aviso=aviso)
        return HTMLResponse(content=html, status_code=502)
    return RedirectResponse(
        url=f"/oracle/comparar/ver?ids={','.join(str(i) for i in lista)}", status_code=303
    )


def _inteiros(valores):
    saida = []
    for valor in valores:
        try:
            saida.append(int(valor))
        except (TypeError, ValueError):
            continue
    return saida


def _recorte_do_lote(dados):
    """base/alvo/q/so_sem, do GET ou do POST. Sem `enviado` nem `alvo` e a
    primeira visita: todos os outros schemas entram como alvo."""
    base = _inteiros([dados.get("base")])
    alvos = _inteiros(dados.getlist("alvo"))
    if not alvos and not dados.get("enviado") and not dados.get("base"):
        alvos = None
    # Trocou o base: os alvos marcados eram os do base anterior -- recomeca com todos
    anterior = _inteiros([dados.get("base_anterior")])
    if base and anterior and base != anterior:
        alvos = None
    return {
        "base_id": base[0] if base else None,
        "alvos": alvos,
        "termo": (dados.get("q") or "").strip(),
        "so_sem": bool(dados.get("so_sem")),
    }


@app.get("/oracle/comparar/lote")
def oracle_comparar_lote(request: Request):
    """Schema base x outros: um conjunto por tabela, para enfileirar."""
    html, status = comparar_view.gerar_lote(
        **_recorte_do_lote(request.query_params), usuario=usuario_mod.identificar(request)
    )
    return HTMLResponse(content=html, status_code=status)


@app.post("/oracle/comparar/lote")
async def oracle_comparar_lote_criar(request: Request):
    """Cria o lote de comparacoes (tarefa comparacao) e dispara o script destacado."""
    usuario = usuario_mod.identificar(request)
    dados = await request.form()
    recorte = _recorte_do_lote(dados)
    par = dados.get("par") or ""
    slug, _, modelo = par.partition("::")
    paralelismo = max(1, min(4, (_inteiros([dados.get("paralelismo")]) or [1])[0]))
    try:
        if not slug or not modelo:
            raise lote_mod.LoteInvalido("Escolha o provedor e o modelo")
        conjuntos = comparacao_mod.conjuntos_validos(dados.getlist("conj"))
        lote_id = lote_mod.criar(
            slug, modelo, paralelismo, None,
            {"base_id": recorte["base_id"], "alvos": recorte["alvos"] or [],
             "termo": recorte["termo"]},
            usuario["email"] if usuario else None,
            tarefa="comparacao",
            conjuntos=conjuntos,
        )
        lote_mod.disparar(lote_id)
    except (lote_mod.LoteInvalido, comparacao_mod.ComparacaoInvalida,
            catalogo_mod.ConsultaFalhou) as falha:
        html, _ = comparar_view.gerar_lote(
            **recorte, paralelismo=paralelismo, usuario=usuario, aviso=_aviso_de(falha)
        )
        return HTMLResponse(content=html, status_code=400)
    return RedirectResponse(url=f"/setup/lote/{lote_id}", status_code=303)


# --------------------------------------------------------------------------
# Fontes de dados > Assistente de consulta
#
# Tambem antes de /oracle/{secao}. As travas (checagem, READ ONLY, teto de
# linhas, mascara, auditoria) vivem em src/consulta.py, nao aqui.
# --------------------------------------------------------------------------


def _email(usuario):
    return usuario["email"] if usuario else None


@app.get("/oracle/consulta")
def oracle_consulta(request: Request, log: int = Query(default=0)):
    """Editor vazio, ou reaberto a partir de uma entrada do historico."""
    usuario = usuario_mod.identificar(request)
    sql = pedido = ""
    if log:
        try:
            entrada = consulta_mod.buscar_log(log, _email(usuario))
        except catalogo_mod.ConsultaFalhou:
            entrada = None
        if entrada:
            sql, pedido = entrada["sql"] or "", entrada["prompt"] or ""
    html, status = consulta_view.gerar(usuario, sql=sql, pedido=pedido,
                                       modo="prompt" if pedido else "sql")
    return HTMLResponse(content=html, status_code=status)


@app.post("/oracle/consulta/sugerir")
def oracle_consulta_sugerir(
    request: Request,
    pedido: str = Form(default=""),
    tabelas: str = Form(default=""),
    provedor: str = Form(default=""),
):
    """A IA escreve o SQL e ele volta para o editor -- sem executar."""
    usuario = usuario_mod.identificar(request)
    comum = dict(pedido=pedido, tabelas=tabelas, provedor=provedor, aba="prompt")
    esquema_id = esquemas_mod.atual_id()
    try:
        if not esquema_id:
            raise consulta_mod.ConsultaRecusada("Escolha um schema no cabeçalho")
        sugestao = consulta_mod.sugerir(
            esquema_id, pedido, provedor or None, tabelas, _email(usuario)
        )
    except (consulta_mod.ConsultaRecusada, ia_view.GeracaoFalhou,
            provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = consulta_view.gerar(usuario, aviso=_aviso_de(falha), **comum)
        return HTMLResponse(content=html, status_code=400)
    html, status = consulta_view.gerar(
        usuario, sql=sugestao["sql"], sugestao=sugestao, modo="prompt", **comum
    )
    return HTMLResponse(content=html, status_code=status)


@app.post("/oracle/consulta/executar")
def oracle_consulta_executar(
    request: Request,
    sql: str = Form(default=""),
    modo: str = Form(default="sql"),
    pedido: str = Form(default=""),
):
    """Roda no Oracle da origem, com todas as travas, e mostra o retorno literal."""
    usuario = usuario_mod.identificar(request)
    modo = modo if modo in ("sql", "prompt") else "sql"
    comum = dict(sql=sql, pedido=pedido, modo=modo)
    esquema_id = esquemas_mod.atual_id()
    try:
        if not esquema_id:
            raise consulta_mod.ConsultaRecusada("Escolha um schema no cabeçalho")
        resultado = consulta_mod.executar(
            esquema_id, sql, _email(usuario), modo=modo, prompt=pedido or None
        )
    except (consulta_mod.ConsultaRecusada, consulta_mod.ConsultaFalhou,
            catalogo_mod.ConsultaFalhou) as falha:
        html, _ = consulta_view.gerar(usuario, aviso=_aviso_de(falha), **comum)
        return HTMLResponse(content=html, status_code=400)
    html, status = consulta_view.gerar(usuario, resultado=resultado, **comum)
    return HTMLResponse(content=html, status_code=status)


@app.get("/oracle/{secao}")
def oracle_secao(
    request: Request,
    secao: str,
    pagina: int = Query(default=1, ge=1),
    por_pagina: int = Query(default=100, ge=10, le=200),
    q: str = Query(default=""),
):
    """Listagem paginada de uma secao do catalogo (objetos, colunas, FKs...)."""
    if secao not in oracle_view.SECOES:
        raise HTTPException(status_code=404, detail=f"secao desconhecida: {secao}")
    html, status = oracle_view.gerar_lista(
        secao,
        pagina,
        por_pagina,
        q,
        _filtros_da_lista(request.query_params),
        usuario_mod.identificar(request),
    )
    return HTMLResponse(content=html, status_code=status)


@app.get("/oracle/objetos/{nome}")
def oracle_objeto(request: Request, nome: str):
    """Detalhe de um objeto: vizinhanca de FKs, descricao por IA e estrutura."""
    html, status = oracle_view.gerar_detalhe(nome, usuario_mod.identificar(request))
    if html is None:
        raise HTTPException(
            status_code=404,
            detail=f"objeto {nome} não existe no schema em uso "
            f"({esquemas_mod.rotulo(esquemas_mod.atual())}). Existe em outro schema? "
            "Troque no cabeçalho.",
        )
    return HTMLResponse(content=html, status_code=status)


@app.post("/oracle/objetos/{nome}/descrever")
def oracle_descrever(request: Request, nome: str, provedor: str = Form(default="")):
    """Gera a descricao pela API do Claude, grava e volta para a pagina.

    O 303 evita que um F5 depois da geracao dispare outra chamada paga.
    """
    usuario = usuario_mod.identificar(request)
    objeto = oracle_view.buscar_objeto(nome, esquemas_mod.atual_id())
    if not objeto:
        raise HTTPException(status_code=404, detail=f"objeto desconhecido: {nome}")

    try:
        descricao, meta = ia_view.descrever(objeto, provedor or None)
        ia_view.gravar(objeto, descricao, meta)
    except (
        ia_view.GeracaoFalhou,
        provedores_mod.ConfiguracaoInvalida,
        catalogo_mod.ConsultaFalhou,
    ) as falha:
        aviso = {
            "motivo": getattr(falha, "motivo", "Não conseguimos gravar a descrição"),
            "detalhe": getattr(falha, "detalhe", str(getattr(falha, "causa", ""))),
        }
        html, _ = oracle_view.gerar_detalhe(nome, usuario, aviso)
        return HTMLResponse(content=html, status_code=502)

    return RedirectResponse(url=f"/oracle/objetos/{nome}", status_code=303)


@app.post("/oracle/objetos/{nome}/vetorizar")
def oracle_vetorizar(request: Request, nome: str, provedor: str = Form(default="")):
    """Vetoriza a descricao da tabela e a de cada campo, e volta para a pagina.

    Mesmo desenho do /descrever, inclusive o 303 contra o F5 -- embedding tambem
    e chamada paga.
    """
    usuario = usuario_mod.identificar(request)
    objeto = oracle_view.buscar_objeto(nome, esquemas_mod.atual_id())
    if not objeto:
        raise HTTPException(status_code=404, detail=f"objeto desconhecido: {nome}")

    try:
        embeddings_mod.vetorizar_objeto(objeto["id"], provedor or None)
    except (
        embeddings_mod.EmbutirFalhou,
        provedores_mod.ConfiguracaoInvalida,
        catalogo_mod.ConsultaFalhou,
    ) as falha:
        aviso = {
            "motivo": getattr(falha, "motivo", "Não conseguimos gravar os vetores"),
            "detalhe": getattr(falha, "detalhe", str(getattr(falha, "causa", ""))),
        }
        html, _ = oracle_view.gerar_detalhe(nome, usuario, aviso)
        return HTMLResponse(content=html, status_code=502)

    return RedirectResponse(url=f"/oracle/objetos/{nome}", status_code=303)


# --------------------------------------------------------------------------
# Setup > AI Providers
# --------------------------------------------------------------------------


def _form_provedor(dados):
    """Campos crus do formulario. A chave nunca e logada nem devolvida a tela."""
    return dict(
        nome=(dados.get("nome") or "").strip(),
        tipo=(dados.get("tipo") or "").strip(),
        url=(dados.get("url") or "").strip(),
        modelos=(dados.get("modelos") or "").strip(),
        capacidade=(dados.get("capacidade") or "llm").strip(),
        chave=(dados.get("chave") or "").strip(),
        ativo=bool(dados.get("ativo")),
    )


@app.get("/setup/provedores")
def setup_provedores(request: Request):
    html, status = setup_view.gerar_lista(usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.get("/setup/provedores/novo")
def setup_provedor_novo(request: Request):
    html, status = setup_view.gerar_form(None, usuario_mod.identificar(request))
    return HTMLResponse(content=html, status_code=status)


@app.post("/setup/provedores")
async def setup_provedor_criar(request: Request):
    usuario = usuario_mod.identificar(request)
    campos = _form_provedor(await request.form())
    try:
        provedores_mod.criar(**campos)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        # Repoe o que foi digitado, menos a chave, para nao perder o preenchimento
        campos.pop("chave")
        html, _ = setup_view.gerar_form(
            None, usuario, aviso=_aviso_de(falha), valores=campos
        )
        return HTMLResponse(content=html, status_code=400)
    return RedirectResponse(url="/setup/provedores", status_code=303)


@app.get("/setup/provedores/{slug}")
def setup_provedor_editar(request: Request, slug: str):
    html, status = setup_view.gerar_form(slug, usuario_mod.identificar(request))
    if html is None:
        raise HTTPException(status_code=404, detail=f"provedor desconhecido: {slug}")
    return HTMLResponse(content=html, status_code=status)


@app.post("/setup/provedores/{slug}")
async def setup_provedor_atualizar(request: Request, slug: str):
    usuario = usuario_mod.identificar(request)
    campos = _form_provedor(await request.form())
    try:
        provedores_mod.atualizar(slug, **campos)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        campos.pop("chave")
        html, _ = setup_view.gerar_form(
            slug, usuario, aviso=_aviso_de(falha), valores=campos
        )
        return HTMLResponse(content=html, status_code=400)
    return RedirectResponse(url="/setup/provedores", status_code=303)


@app.post("/setup/provedores/{slug}/excluir")
def setup_provedor_excluir(request: Request, slug: str):
    try:
        provedores_mod.excluir(slug)
    except catalogo_mod.ConsultaFalhou as falha:
        html, _ = setup_view.gerar_lista(
            usuario_mod.identificar(request), aviso=_aviso_de(falha)
        )
        return HTMLResponse(content=html, status_code=502)
    return RedirectResponse(url="/setup/provedores", status_code=303)


# --------------------------------------------------------------------------
# Setup > Servidores
# --------------------------------------------------------------------------

SERVIDORES = "/setup/servidores"


def _form_servidor(dados):
    """Campos crus do formulario. A senha nunca e logada nem devolvida a tela."""
    return dict(
        tipo=(dados.get("tipo") or "").strip(),
        host=(dados.get("host") or "").strip(),
        porta=(dados.get("porta") or "").strip(),
        base=(dados.get("base") or "").strip(),
        nome=(dados.get("nome") or "").strip(),
        ativo=bool(dados.get("ativo")),
        usuario=(dados.get("usuario") or "").strip(),
        senha_fonte=(dados.get("senha_fonte") or "").strip(),
        senha_ref=(dados.get("senha_ref") or "").strip(),
        usuario_gcp=(dados.get("usuario_gcp") or "").strip(),
        senha_fonte_gcp=(dados.get("senha_fonte_gcp") or "").strip(),
        senha_ref_gcp=(dados.get("senha_ref_gcp") or "").strip(),
        senha=dados.get("senha") or "",
    )


def _html(par):
    html, status = par
    if html is None:
        raise HTTPException(status_code=404, detail="servidor desconhecido")
    return HTMLResponse(content=html, status_code=status)


@app.get("/setup/servidores")
def setup_servidores(request: Request):
    return _html(setup_servidores_view.gerar_lista(usuario_mod.identificar(request)))


@app.get("/setup/servidores/novo")
def setup_servidor_novo(request: Request):
    return _html(setup_servidores_view.gerar_form(None, usuario_mod.identificar(request)))


@app.post("/setup/servidores")
async def setup_servidor_criar(request: Request):
    usuario = usuario_mod.identificar(request)
    campos = _form_servidor(await request.form())
    try:
        servidor_id = servidores_mod.criar(**campos)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        campos.pop("senha")
        html, _ = setup_servidores_view.gerar_form(
            None, usuario, aviso=_aviso_de(falha), valores=campos
        )
        return HTMLResponse(content=html, status_code=400)
    return RedirectResponse(url=f"{SERVIDORES}/{servidor_id}", status_code=303)


@app.get("/setup/servidores/{servidor_id}")
def setup_servidor_editar(request: Request, servidor_id: int):
    return _html(
        setup_servidores_view.gerar_form(servidor_id, usuario_mod.identificar(request))
    )


@app.post("/setup/servidores/{servidor_id}")
async def setup_servidor_atualizar(request: Request, servidor_id: int):
    usuario = usuario_mod.identificar(request)
    campos = _form_servidor(await request.form())
    try:
        servidores_mod.atualizar(servidor_id, **campos)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        campos.pop("senha")
        html, _ = setup_servidores_view.gerar_form(
            servidor_id, usuario, aviso=_aviso_de(falha), valores=campos
        )
        return HTMLResponse(content=html or "", status_code=400 if html else 404)
    return RedirectResponse(url=f"{SERVIDORES}/{servidor_id}", status_code=303)


@app.post("/setup/servidores/{servidor_id}/testar")
async def setup_servidor_testar(request: Request, servidor_id: int):
    """Testa o perfil pedido pelo botao; sem ele, o do ambiente em que o app roda."""
    usuario = usuario_mod.identificar(request)
    perfil = (await request.form()).get("perfil")
    if perfil not in servidores_mod.PERFIS:
        perfil = None
    try:
        ok, detalhe, ms = servidores_mod.testar(servidor_id, perfil)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        return _html(
            setup_servidores_view.gerar_form(servidor_id, usuario, aviso=_aviso_de(falha))
        )
    return _html(
        setup_servidores_view.gerar_form(
            servidor_id, usuario, teste={"ok": ok, "detalhe": detalhe, "ms": ms}
        )
    )


@app.post("/setup/servidores/{servidor_id}/excluir")
def setup_servidor_excluir(request: Request, servidor_id: int):
    usuario = usuario_mod.identificar(request)
    try:
        servidores_mod.excluir(servidor_id)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = setup_servidores_view.gerar_form(servidor_id, usuario, aviso=_aviso_de(falha))
        return HTMLResponse(content=html or "", status_code=409 if html else 404)
    return RedirectResponse(url=SERVIDORES, status_code=303)


@app.post("/setup/servidores/{servidor_id}/esquemas")
async def setup_esquema_criar(request: Request, servidor_id: int):
    usuario = usuario_mod.identificar(request)
    dados = await request.form()
    try:
        servidores_mod.criar_esquema(servidor_id, dados.get("nome"))
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = setup_servidores_view.gerar_form(servidor_id, usuario, aviso=_aviso_de(falha))
        return HTMLResponse(content=html or "", status_code=400 if html else 404)
    return RedirectResponse(url=f"{SERVIDORES}/{servidor_id}", status_code=303)


@app.post("/setup/servidores/{servidor_id}/esquemas/{esquema_id}/excluir")
def setup_esquema_excluir(request: Request, servidor_id: int, esquema_id: int):
    usuario = usuario_mod.identificar(request)
    try:
        servidores_mod.excluir_esquema(servidor_id, esquema_id)
    except (provedores_mod.ConfiguracaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = setup_servidores_view.gerar_form(servidor_id, usuario, aviso=_aviso_de(falha))
        return HTMLResponse(content=html or "", status_code=409 if html else 404)
    return RedirectResponse(url=f"{SERVIDORES}/{servidor_id}", status_code=303)


def _aviso_de(falha):
    return {
        "motivo": getattr(falha, "motivo", "Não conseguimos gravar"),
        "detalhe": getattr(falha, "detalhe", str(getattr(falha, "causa", ""))),
    }


# --------------------------------------------------------------------------
# Setup > Lote de descricoes
# --------------------------------------------------------------------------


def _filtros_do_lote(dados):
    """Nomes marcados -> chaves internas. Serve tanto a querystring quanto o POST."""
    return {chave for chave, param, _, _ in lote_mod.FILTROS if dados.get(param)}


def _tarefa_do_lote(dados):
    tarefa = (dados.get("tarefa") or "descricao").strip()
    return tarefa if tarefa in lote_mod.TAREFAS_POR_OBJETO else "descricao"


@app.get("/setup/lote")
def setup_lote(
    request: Request,
    q: str = Query(default=""),
    paralelismo: int = Query(default=4, ge=1, le=16),
):
    """Selecao das tabelas do lote.

    Os filtros saem direto da querystring em vez de virarem um parametro cada:
    assim lote_mod.FILTROS continua sendo a unica lista a manter quando entra um
    filtro novo.
    """
    html, status = setup_lote_view.gerar_selecao(
        _filtros_do_lote(request.query_params),
        q.strip(),
        paralelismo,
        usuario_mod.identificar(request),
        tarefa=_tarefa_do_lote(request.query_params),
    )
    return HTMLResponse(content=html, status_code=status)


@app.post("/setup/lote")
async def setup_lote_criar(request: Request):
    """Cria o lote e dispara o script destacado."""
    usuario = usuario_mod.identificar(request)
    dados = await request.form()
    ativos = _filtros_do_lote(dados)
    termo = (dados.get("q") or "").strip()
    tarefa = _tarefa_do_lote(dados)
    par = dados.get("par") or ""
    slug, _, modelo = par.partition("::")
    paralelismo = max(1, min(16, int(dados.get("paralelismo") or 4)))

    if dados.get("todas"):
        objetos = lote_mod.ids_do_recorte(esquemas_mod.atual_id(), ativos, termo)
    else:
        objetos = [int(v) for v in dados.getlist("objetos")]

    try:
        if not slug or not modelo:
            raise lote_mod.LoteInvalido("Escolha o provedor e o modelo")
        lote_id = lote_mod.criar(
            slug,
            modelo,
            paralelismo,
            objetos,
            {
                "filtros": sorted(ativos),
                "termo": termo,
                "todas": bool(dados.get("todas")),
                # Registro de qual schema era o pre-filtro quando o lote foi criado
                "esquema_id": esquemas_mod.atual_id(),
            },
            usuario["email"] if usuario else None,
            tarefa=tarefa,
        )
        lote_mod.disparar(lote_id)
    except (lote_mod.LoteInvalido, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = setup_lote_view.gerar_selecao(
            ativos, termo, paralelismo, usuario, aviso=_aviso_de(falha), tarefa=tarefa
        )
        return HTMLResponse(content=html, status_code=400)

    return RedirectResponse(url=f"/setup/lote/{lote_id}", status_code=303)


@app.get("/setup/lote/{lote_id}")
def setup_lote_progresso(request: Request, lote_id: int):
    """Acompanhamento; recarrega sozinha enquanto o lote roda."""
    html, status = setup_lote_view.gerar_progresso(lote_id, usuario_mod.identificar(request))
    if html is None:
        raise HTTPException(status_code=404, detail=f"lote desconhecido: {lote_id}")
    return HTMLResponse(content=html, status_code=status)


@app.post("/setup/lote/{lote_id}/retomar")
def setup_lote_retomar(request: Request, lote_id: int):
    """Continua um lote cancelado pelos itens ainda pendentes."""
    try:
        lote = lote_mod.buscar(lote_id)
        if not lote:
            raise HTTPException(status_code=404, detail=f"lote desconhecido: {lote_id}")
        # A trava e por tarefa: um lote de comparacao nao espera um de descricao
        aberto = lote_mod.em_andamento(lote["tarefa"])
        if aberto:
            raise lote_mod.LoteInvalido(f"O lote #{aberto['id']} ainda está em andamento")
        lote_mod.disparar(lote_id, retomar=True)
    except (lote_mod.LoteInvalido, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = setup_lote_view.gerar_progresso(
            lote_id, usuario_mod.identificar(request), aviso=_aviso_de(falha)
        )
        return HTMLResponse(content=html, status_code=400)
    return RedirectResponse(url=f"/setup/lote/{lote_id}", status_code=303)


@app.post("/setup/lote/{lote_id}/cancelar")
def setup_lote_cancelar(request: Request, lote_id: int):
    try:
        lote_mod.cancelar(lote_id)
    except catalogo_mod.ConsultaFalhou as falha:
        html, _ = setup_lote_view.gerar_progresso(
            lote_id, usuario_mod.identificar(request), aviso=_aviso_de(falha)
        )
        return HTMLResponse(content=html, status_code=502)
    return RedirectResponse(url=f"/setup/lote/{lote_id}", status_code=303)


# --------------------------------------------------------------------------
# Setup > Importar dados
# --------------------------------------------------------------------------

IMPORTAR = "/setup/importar"


def _esquema_do_form(dados):
    try:
        return int(dados.get("esquema_id") or "")
    except ValueError as e:
        raise importacao_mod.ImportacaoInvalida("Escolha o schema") from e


@app.get(IMPORTAR)
def setup_importar(request: Request):
    return _html(setup_importar_view.gerar_form(usuario_mod.identificar(request)))


@app.post(IMPORTAR)
async def setup_importar_criar(request: Request):
    """Cria a linha da importacao e dispara o job (ou o processo local)."""
    usuario = usuario_mod.identificar(request)
    dados = await request.form()
    try:
        esquema_id = _esquema_do_form(dados)
        modo, parametros = importacao_mod.parametros_do_form(dados)
        importacao_id = importacao_mod.criar(
            esquema_id, modo, parametros, usuario["email"] if usuario else None
        )
        importacao_mod.disparar(importacao_id)
    except (importacao_mod.ImportacaoInvalida, catalogo_mod.ConsultaFalhou) as falha:
        html, _ = setup_importar_view.gerar_form(
            usuario, aviso=_aviso_de(falha), valores=dict(dados)
        )
        return HTMLResponse(content=html, status_code=400)
    return RedirectResponse(url=f"{IMPORTAR}/{importacao_id}", status_code=303)


@app.post(f"{IMPORTAR}/testar")
async def setup_importar_testar(request: Request):
    """Conexao com o servidor do schema, no perfil deste ambiente (make catalogo_env)."""
    usuario = usuario_mod.identificar(request)
    dados = await request.form()
    try:
        ok, mensagem, ms = importacao_mod.testar_conexao(_esquema_do_form(dados))
    except (importacao_mod.ImportacaoInvalida, provedores_mod.ConfiguracaoInvalida,
            catalogo_mod.ConsultaFalhou) as falha:
        ok, mensagem, ms = False, _aviso_de(falha)["motivo"], None
    resultado = {"motivo": "Conexão OK" if ok else "Conexão falhou",
                 "detalhe": mensagem + (f" ({ms:.0f} ms)" if ms is not None else "")}
    html, _ = setup_importar_view.gerar_form(
        usuario, valores=dict(dados),
        **({"sucesso": resultado} if ok else {"aviso": resultado}),
    )
    return HTMLResponse(content=html, status_code=200 if ok else 502)


@app.post(f"{IMPORTAR}/ddl")
async def setup_importar_ddl(request: Request):
    """Reaplica scripts/catalogo_schema.sql (make schema), sem tocar na origem."""
    usuario = usuario_mod.identificar(request)
    dados = await request.form()
    ok, detalhe = importacao_mod.aplicar_ddl()
    resultado = {"motivo": "DDL aplicado" if ok else "DDL não aplicado", "detalhe": detalhe}
    html, _ = setup_importar_view.gerar_form(
        usuario, valores=dict(dados),
        **({"sucesso": resultado} if ok else {"aviso": resultado}),
    )
    return HTMLResponse(content=html, status_code=200 if ok else 502)


@app.get(IMPORTAR + "/{importacao_id}")
def setup_importar_progresso(request: Request, importacao_id: int):
    """Acompanhamento; recarrega sozinha enquanto a importacao roda."""
    html, status = setup_importar_view.gerar_progresso(
        importacao_id, usuario_mod.identificar(request)
    )
    if html is None:
        raise HTTPException(status_code=404, detail=f"importacao desconhecida: {importacao_id}")
    return HTMLResponse(content=html, status_code=status)


@app.post(IMPORTAR + "/{importacao_id}/cancelar")
def setup_importar_cancelar(request: Request, importacao_id: int):
    usuario = usuario_mod.identificar(request)
    try:
        importacao_mod.cancelar(importacao_id, usuario["email"] if usuario else None)
    except catalogo_mod.ConsultaFalhou as falha:
        html, _ = setup_importar_view.gerar_progresso(
            importacao_id, usuario, aviso=_aviso_de(falha)
        )
        return HTMLResponse(content=html, status_code=502)
    return RedirectResponse(url=f"{IMPORTAR}/{importacao_id}", status_code=303)


# --------------------------------------------------------------------------
# API JSON
#
# Fora do padrao do resto do arquivo de proposito: as outras rotas respondem
# HTML e redirecionam com 303 para o navegador nao repetir a acao no F5. Estas
# aqui nao tem navegador do outro lado -- respondem JSON e devolvem o erro no
# corpo, nao numa pagina.
# --------------------------------------------------------------------------


def _autor(request):
    """Email de quem chamou, quando o proxy identificou. Vai para editado_por."""
    usuario = usuario_mod.identificar(request)
    return usuario["email"] if usuario else None


@app.post("/api/objetos/descricoes")
def api_descricoes(request: Request, corpo: api_mod.Requisicao):
    """Recebe descricao e rotulo prontos e revetoriza com o modelo configurado.

    Status: 200 tudo gravado, 207 parte, 502 nenhum. Ver src/api.py para a
    semantica do merge -- o que o corpo nao traz nao muda.
    """
    try:
        resposta, status = api_mod.aplicar(corpo, _autor(request))
    except (api_mod.EntradaInvalida, provedores_mod.ConfiguracaoInvalida) as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=400)
    except catalogo_mod.ConsultaFalhou as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=502)
    return JSONResponse(resposta, status_code=status)


@app.post("/api/dicionario/descricoes")
def api_dicionario(request: Request, corpo: api_mod.RequisicaoDicionario):
    """Mesma escrita da rota acima, na forma da planilha: uma linha por coluna.

    Grava so os campos -- rotulo, resumo e funcao da tabela ficam como estao --
    e revetoriza cada tabela tocada uma vez so.
    """
    try:
        resposta, status = api_mod.aplicar_dicionario(corpo, _autor(request))
    except (api_mod.EntradaInvalida, provedores_mod.ConfiguracaoInvalida) as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=400)
    except catalogo_mod.ConsultaFalhou as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=502)
    return JSONResponse(resposta, status_code=status)


@app.get("/api/config")
def api_config_ler():
    """Configuracao geral inteira, com as chaves nao gravadas como ""."""
    try:
        return JSONResponse(config_mod.todas())
    except catalogo_mod.ConsultaFalhou as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=502)


@app.put("/api/config")
def api_config_gravar(request: Request, corpo: dict[str, str]):
    """Grava as chaves recebidas. Valor vazio volta a chave ao padrao.

    Uma chave desconhecida recusa o request INTEIRO, antes de gravar qualquer
    uma: gravar metade de uma configuracao e pior do que nao gravar nada.
    """
    try:
        for chave, valor in corpo.items():
            config_mod.validar(chave, (valor or "").strip())
        for chave, valor in corpo.items():
            config_mod.definir(chave, valor, _autor(request))
        return JSONResponse(config_mod.todas())
    except provedores_mod.ConfiguracaoInvalida as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=400)
    except catalogo_mod.ConsultaFalhou as falha:
        return JSONResponse({"erro": _aviso_de(falha)}, status_code=502)
