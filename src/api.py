"""API JSON de escrita do catalogo: descricao e rotulo vindos de fora.

O resto do app e HTML com POST de formulario. Aqui e JSON, para quem mantem a
documentacao fora da tela -- planilha revisada pela area de negocio, script de
migracao, outro sistema.

Sao dois endpoints sobre a MESMA escrita, em duas formas:

  POST /api/objetos/descricoes   -- o objeto inteiro, com os campos aninhados
  POST /api/dicionario/descricoes -- uma linha por (objeto, coluna), como a
                                     planilha que sai de catalogo.vw_dicionario

Como isto difere de /oracle/objetos/{nome}/descrever: la a IA escreve o texto e o
usuario escolhe o provedor num select. Aqui o texto ja vem pronto, e nao ha tela
onde escolher nada -- por isso o modelo de embedding sai da configuracao geral
(src/config.py). Um texto novo sem vetor novo seria pior do que nao aceitar o
texto: a busca semantica continuaria devolvendo o resultado antigo, sem nada na
tela dizendo que o indice esta velho.

Semantica da escrita, em uma frase: o que o corpo NAO traz nao muda.

  - Campo ausente fica como esta. Campo presente com "" apaga o texto.
  - `campos` casa por nome de coluna: mandar tres colunas nao apaga as outras
    setenta e sete. Coluna com descricao "" sai da lista.
  - provedor/modelo/gerado_em de catalogo.descricao_ia NAO sao tocados numa
    edicao: eles dizem quem GEROU o texto original. Quem editou depois vai para
    editado_por/editado_em.
"""

import json
import logging

from pydantic import BaseModel, ConfigDict

from . import catalogo, config, embeddings, oracle, provedores

logger = logging.getLogger(__name__)

# Objetos por chamada. O custo nao e o INSERT, e a vetorizacao: cada objeto e ao
# menos uma ida ate a API de embeddings, e o request fica aberto ate a ultima.
# Lote maior do que isto e caso para Setup > Lote de vetores, que roda destacado.
TETO_OBJETOS = 50

# Proveniencia de uma descricao que nunca passou por IA. Vale so no INSERT: numa
# edicao, provedor e modelo ficam com o que a IA gravou.
PROVEDOR_EXTERNO = "api"
MODELO_EXTERNO = "externo"


class CampoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coluna: str
    descricao: str


class VinculoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tabela: str
    motivo: str


class ObjetoEntrada(BaseModel):
    """`None` e ausencia, e nao valor: so o que veio no corpo entra no UPDATE.

    Por isso todo campo opcional nasce None em vez de "" -- sem essa distincao
    nao haveria como diferenciar "nao mexa no resumo" de "apague o resumo".
    """

    model_config = ConfigDict(extra="forbid")

    nome: str
    rotulo: str | None = None
    resumo: str | None = None
    funcao: str | None = None
    dominio: str | None = None
    dependencias: list[VinculoEntrada] | None = None
    dependentes: list[VinculoEntrada] | None = None
    campos: list[CampoEntrada] | None = None


class Requisicao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objetos: list[ObjetoEntrada]
    # Desligar serve para carga em massa, quando a intencao e vetorizar tudo
    # depois num lote so. O vetor fica velho ate la -- e o campo existe
    # justamente para que isso seja uma escolha declarada, nao um efeito.
    vetorizar: bool = True


class EntradaInvalida(Exception):
    """Mesmo contrato de ia.GeracaoFalhou e embeddings.EmbutirFalhou."""

    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


# --------------------------------------------------------------------------
# Gravacao
# --------------------------------------------------------------------------

SQL_DESCRICAO_ATUAL = """
SELECT rotulo, resumo, funcao, dominio, dependencias, dependentes, campos
  FROM catalogo.descricao_ia
 WHERE objeto_id = %s
"""

SQL_NOMES_DE_COLUNA = "SELECT nome FROM catalogo.coluna WHERE objeto_id = %s"

# O DO UPDATE nao lista provedor, modelo, gerado_em, linhas_no_prompt nem os
# tokens de proposito: sao a ficha da geracao por IA, e uma edicao de texto nao
# tem o que dizer sobre eles.
SQL_GRAVAR = """
INSERT INTO catalogo.descricao_ia
    (objeto_id, rotulo, resumo, funcao, dominio, dependencias, dependentes, campos,
     provedor, modelo, colunas_descritas, linhas_no_prompt, editado_por, editado_em)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, now())
ON CONFLICT (objeto_id) DO UPDATE SET
    rotulo            = EXCLUDED.rotulo,
    resumo            = EXCLUDED.resumo,
    funcao            = EXCLUDED.funcao,
    dominio           = EXCLUDED.dominio,
    dependencias      = EXCLUDED.dependencias,
    dependentes       = EXCLUDED.dependentes,
    campos            = EXCLUDED.campos,
    colunas_descritas = EXCLUDED.colunas_descritas,
    editado_por       = EXCLUDED.editado_por,
    editado_em        = now()
"""


def mesclar_campos(atuais, novos, nomes_validos):
    """Casa por nome de coluna. Descricao vazia remove; o resto e acrescimo.

    Substituir a lista inteira pelo que veio seria o caminho curto, e apagaria
    silenciosamente a descricao de toda coluna que o corpo nao citou -- que e o
    caso normal quando alguem corrige tres campos de uma tabela de oitenta.
    """
    desconhecidas = [campo.coluna for campo in novos if campo.coluna not in nomes_validos]
    if desconhecidas:
        raise EntradaInvalida(
            f"Coluna inexistente: {', '.join(sorted(desconhecidas))}",
            "O nome tem de bater com catalogo.coluna, inclusive na caixa "
            "(no Oracle os nomes estão em maiúsculas).",
        )

    por_nome = {campo["coluna"]: campo["descricao"] for campo in atuais}
    for campo in novos:
        texto = campo.descricao.strip()
        if texto:
            por_nome[campo.coluna] = texto
        else:
            por_nome.pop(campo.coluna, None)
    return [{"coluna": nome, "descricao": texto} for nome, texto in por_nome.items()]


def _escolher(novo, atual, padrao=""):
    """Ausente (None) mantem o que esta gravado; presente vence, inclusive "" ."""
    if novo is None:
        return atual if atual is not None else padrao
    return novo.strip() if isinstance(novo, str) else novo


def gravar_descricao(entrada, autor=None):
    """Mescla o que veio com o que esta gravado. Devolve (objeto, criada)."""
    objeto = oracle.buscar_objeto(entrada.nome)
    if not objeto:
        raise EntradaInvalida(
            f"Objeto desconhecido: '{entrada.nome}'",
            "O nome tem de bater com catalogo.objeto, inclusive na caixa.",
        )

    atual = catalogo.um(SQL_DESCRICAO_ATUAL, (objeto["id"],), f"descrição de {objeto['nome']}")
    criada = atual is None
    atual = atual or {}

    resumo = _escolher(entrada.resumo, atual.get("resumo"))
    if criada and not resumo:
        # Vale para os dois endpoints, e por isso nao fala em 'resumo' como campo
        # obrigatorio: quem vem pelo dicionario nao tem onde informar um.
        raise EntradaInvalida(
            f"'{objeto['nome']}' ainda não tem descrição de tabela",
            "Descreva a tabela antes dos campos: POST /api/objetos/descricoes com "
            "'resumo', ou o botão Gerar descrição na página do objeto. Sem resumo "
            "não há texto para representar a tabela no vetor.",
        )

    nomes_validos = {
        linha["nome"]
        for linha in catalogo.consultar(
            SQL_NOMES_DE_COLUNA, (objeto["id"],), f"colunas de {objeto['nome']}"
        )
    }
    campos = (
        atual.get("campos") or []
        if entrada.campos is None
        else mesclar_campos(atual.get("campos") or [], entrada.campos, nomes_validos)
    )

    def como_json(novos, chave):
        if novos is None:
            return json.dumps(atual.get(chave) or [], ensure_ascii=False)
        return json.dumps([v.model_dump() for v in novos], ensure_ascii=False)

    catalogo.executar(
        SQL_GRAVAR,
        (
            objeto["id"],
            _escolher(entrada.rotulo, atual.get("rotulo")),
            resumo,
            _escolher(entrada.funcao, atual.get("funcao")),
            _escolher(entrada.dominio, atual.get("dominio"), None),
            como_json(entrada.dependencias, "dependencias"),
            como_json(entrada.dependentes, "dependentes"),
            json.dumps(campos, ensure_ascii=False),
            PROVEDOR_EXTERNO,
            MODELO_EXTERNO,
            len(campos),
            autor,
        ),
        f"descrição de {objeto['nome']} via API",
    )
    logger.info(
        "descrição de %s %s por %s (%s campos)",
        objeto["nome"], "criada" if criada else "atualizada", autor or "anônimo", len(campos),
    )
    return objeto, criada


# --------------------------------------------------------------------------
# Orquestracao
# --------------------------------------------------------------------------


def _erro(falha):
    """`tipo` separa culpa do cliente de culpa de terceiro.

    Sem isso o status da resposta nao teria como escolher entre 400 e 502 num
    lote que falhou inteiro -- e nome de tabela errado devolvendo 502 mandaria o
    cliente tentar de novo para sempre.
    """
    return {
        "tipo": "entrada" if isinstance(falha, EntradaInvalida) else "upstream",
        "motivo": getattr(falha, "motivo", "Falha inesperada"),
        "detalhe": getattr(falha, "detalhe", str(getattr(falha, "causa", falha))),
    }


def _um_objeto(entrada, par, vetorizar, autor, extras=None):
    """Grava a descricao mesclada de um objeto e revetoriza. Devolve o item da resposta."""
    try:
        objeto, criada = gravar_descricao(entrada, autor)
    except (EntradaInvalida, catalogo.ConsultaFalhou) as falha:
        return {"nome": entrada.nome, "ok": False, "erro": _erro(falha), **(extras or {})}

    item = {"nome": objeto["nome"], "ok": True, "criada": criada,
            "vetores": None, **(extras or {})}
    if vetorizar:
        try:
            item["vetores"] = embeddings.vetorizar_objeto(objeto["id"], par)
        except (embeddings.EmbutirFalhou, provedores.ConfiguracaoInvalida,
                catalogo.ConsultaFalhou) as falha:
            # O texto ja esta gravado e o embedding_hash continua o antigo, entao
            # a proxima vetorizacao refaz este objeto sozinha. Por isso a falha do
            # vetor nao desfaz a escrita -- so marca o item.
            item["ok"] = False
            item["erro"] = _erro(falha)
    return item


def _resumo(resultados, par, vetorizar):
    """Corpo e status da resposta.

    O status resume, para que um cliente que so olha o codigo nao tome falha por
    sucesso: 200 tudo certo, 207 misto, 400 nada gravado por culpa do corpo, 502
    nada gravado por culpa do provedor ou do catalogo.
    """
    passaram = sum(1 for item in resultados if item["ok"])
    if passaram == len(resultados):
        status = 200
    elif passaram:
        status = 207            # Multi-Status: o corpo diz item a item quem passou
    elif all(item["erro"]["tipo"] == "entrada" for item in resultados):
        status = 400            # nada gravado, e a culpa e do corpo enviado
    else:
        status = 502            # o provedor ou o catalogo e que falharam
    return {
        "gravados": passaram,
        "total": len(resultados),
        "modelo_de_vetor": par or ("padrão do provedor" if vetorizar else None),
        "objetos": resultados,
    }, status


def _conferir_teto(quantos, teto, oque):
    if quantos > teto:
        raise EntradaInvalida(
            f"{oque} demais: {quantos}, o teto é {teto}",
            "Quebre em chamadas menores, ou use Setup › Lote de vetores para "
            "vetorizar em massa depois de gravar com vetorizar=false.",
        )


def aplicar(requisicao, autor=None):
    """Grava cada objeto e revetoriza. Devolve (corpo, status HTTP).

    Um objeto ruim nao derruba o lote: cada item traz o proprio `ok`.
    """
    if not requisicao.objetos:
        raise EntradaInvalida("Nenhum objeto no corpo", "Mande ao menos um item em 'objetos'.")
    _conferir_teto(len(requisicao.objetos), TETO_OBJETOS, "Objetos")

    par = config.par_de_embedding() if requisicao.vetorizar else None
    resultados = [
        _um_objeto(entrada, par, requisicao.vetorizar, autor)
        for entrada in requisicao.objetos
    ]
    return _resumo(resultados, par, requisicao.vetorizar)


# --------------------------------------------------------------------------
# Dicionario de dados: as mesmas descricoes de campo, endereçadas por linha
#
# O endpoint de cima recebe o objeto inteiro, com os campos aninhados. Este
# recebe a planilha: uma linha por (objeto, coluna), que e a forma de
# catalogo.vw_dicionario -- exportar o dicionario, preencher a coluna de
# descricao e devolver o arquivo nao deveria exigir remontar um JSON aninhado.
#
# O destino e o MESMO: descricao_ia.campos, o jsonb por objeto. Escrever direto
# em catalogo.coluna.descricao_ia seria o caminho obvio e estaria errado duas
# vezes -- vw_dicionario le o jsonb, entao a tela nao mostraria nada; e o
# SQL_SINCRONIZAR_CAMPOS da proxima vetorizacao reescreveria a coluna a partir do
# jsonb, apagando o texto em silencio.
# --------------------------------------------------------------------------

# Colunas por chamada. Independente de TETO_OBJETOS porque a planilha e larga
# por natureza: uma tabela legada sozinha passa de 300 campos.
TETO_COLUNAS = 500


class LinhaDicionario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objeto: str
    coluna: str
    # Aqui a descricao e obrigatoria: a linha existe para trazer uma. "" continua
    # significando "apague esta descricao", como no outro endpoint.
    descricao: str


class RequisicaoDicionario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    colunas: list[LinhaDicionario]
    vetorizar: bool = True


def agrupar_por_objeto(linhas):
    """[{objeto, coluna, descricao}] -> {objeto: [CampoEntrada]}, na ordem de chegada.

    Agrupar antes de gravar e o que torna a planilha barata: uma escrita e uma
    ida a API de embeddings por TABELA, e nao por linha. Linha repetida para a
    mesma coluna vale a ultima, que e o que se espera de uma planilha.
    """
    por_objeto = {}
    for linha in linhas:
        por_objeto.setdefault(linha.objeto, []).append(
            CampoEntrada(coluna=linha.coluna, descricao=linha.descricao)
        )
    return por_objeto


def aplicar_dicionario(requisicao, autor=None):
    """Grava as descricoes de campo vindas em forma de planilha e revetoriza.

    So mexe em `campos`: rotulo, resumo e funcao da tabela ficam como estao -- e
    a mesma semantica de ausencia do outro endpoint, e aqui ela e total, porque
    uma linha de dicionario nao tem o que dizer sobre a tabela.
    """
    if not requisicao.colunas:
        raise EntradaInvalida("Nenhuma coluna no corpo", "Mande ao menos um item em 'colunas'.")
    _conferir_teto(len(requisicao.colunas), TETO_COLUNAS, "Colunas")

    por_objeto = agrupar_por_objeto(requisicao.colunas)
    _conferir_teto(len(por_objeto), TETO_OBJETOS, "Objetos")

    par = config.par_de_embedding() if requisicao.vetorizar else None
    resultados = []
    for nome, campos in por_objeto.items():
        entrada = ObjetoEntrada(nome=nome, campos=campos)
        extras = {"colunas": [campo.coluna for campo in campos]}
        resultados.append(
            _um_objeto(entrada, par, requisicao.vetorizar, autor, extras)
        )
    return _resumo(resultados, par, requisicao.vetorizar)
