
import os

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import layout
from . import lote as lote_mod
from . import log as log_mod
from . import api as api_mod
from . import catalogo as catalogo_mod
from . import config as config_mod
from . import debug as debug_view
from . import embeddings as embeddings_mod
from . import grafo as grafo_mod
from . import health as health_view
from . import home as home_view
from . import ia as ia_view
from . import oracle as oracle_view
from . import provedores as provedores_mod
from . import setup as setup_view
from . import setup_lote as setup_lote_view
from . import usuario as usuario_mod

# Antes de qualquer rota: sem isto os logger.error dos modulos nao saem formatados
log_mod.configurar()

app = FastAPI()

# Ativos da aplicação (src/static)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Design system Opalus servido a partir da raiz do projeto
DS_DIR = os.path.join(BASE_DIR, "..", "ds_opalus")
app.mount("/ds-static", StaticFiles(directory=DS_DIR), name="ds-static")


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
        return JSONResponse(grafo_mod.grafo_completo())
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
        raise HTTPException(status_code=404, detail=f"objeto desconhecido: {nome}")
    return HTMLResponse(content=html, status_code=status)


@app.post("/oracle/objetos/{nome}/descrever")
def oracle_descrever(request: Request, nome: str, provedor: str = Form(default="")):
    """Gera a descricao pela API do Claude, grava e volta para a pagina.

    O 303 evita que um F5 depois da geracao dispare outra chamada paga.
    """
    usuario = usuario_mod.identificar(request)
    objeto = oracle_view.buscar_objeto(nome)
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
    objeto = oracle_view.buscar_objeto(nome)
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
    return tarefa if tarefa in lote_mod.TAREFAS else "descricao"


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
        objetos = lote_mod.ids_do_recorte(ativos, termo)
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
            {"filtros": sorted(ativos), "termo": termo, "todas": bool(dados.get("todas"))},
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
        aberto = lote_mod.em_andamento()
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
