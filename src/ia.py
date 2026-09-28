"""Descricao dos campos de uma tabela, gerada por uma API de IA.

Este modulo e o USO; src/provedores.py e a CONFIGURACAO (o cadastro em
Setup > AI Providers, com a chave cifrada). Aqui ficam so os adaptadores por
protocolo -- anthropic e openai -- e a montagem do prompt.

O nucleo continua sendo o ORCAMENTO do prompt: a amostra do catalogo varia 170x
de tamanho entre objetos (mediana 3 KB, maximo 569 KB em TDWD_PLENO, 307 colunas).
Metadado de coluna vai inteiro; a amostra entra linha a linha ate um teto.

O que sai do ambiente: estrutura + as linhas de amostra como estao no catalogo --
que e o dado REAL da origem. O mascaramento saiu da extracao por decidir pelo nome
da coluna e errar dos dois lados; nada substitui o valor antes de ele chegar aqui.
"""

import json
import logging
import random
import re
import time

from pydantic import BaseModel, ValidationError

from . import catalogo, provedores

logger = logging.getLogger(__name__)

# Teto do prompt INTEIRO, nao so da amostra. O metadado das colunas e obrigatorio
# e vem primeiro; a amostra fica com o que sobrar. Assim tabela larga recebe pouca
# ou nenhuma amostra automaticamente.
#
# Isto nao e economia de token, e o que faz a feature funcionar: modelo raciocinante
# pensa proporcionalmente ao tamanho da entrada, e o raciocinio consome o mesmo
# orcamento da resposta. Medido em CAPADMISSION (194 colunas) no deepseek-v4-flash:
#   prompt 32.796 b -> stop=max_tokens, 16.000 tokens de saida, ZERO texto
#   prompt  5.658 b -> stop=end_turn,   13.964 tokens de saida, resposta completa
TENTATIVAS = 3

# Espera entre tentativas, exponencial com jitter. Mesma base de embeddings.py.
ESPERA_BASE = 2.0

TETO_PROMPT_BYTES = 64_000
MAX_TOKENS = 128_000
# Endpoint compativel raciocina dentro do mesmo orcamento da resposta, entao
# precisa de mais folga -- e acima de ~16k o SDK exige streaming, que tambem
# evita estourar o timeout HTTP quando o modelo pensa por minutos.
MAX_TOKENS_COMPATIVEL = 256_000

INSTRUCOES = """Você é um analista de dados documentando um schema Oracle legado de \
um sistema de saúde (geriatria, internação domiciliar). Os nomes de tabela e coluna \
são crípticos e abreviados; seu trabalho é dizer o que cada campo guarda de fato.

Regras:
- Escreva em português do Brasil, direto, sem rodeio nem repetir o nome da coluna.
- Uma frase por campo. Diga o conteúdo e, quando a coluna for chave estrangeira, \
diga para que entidade ela aponta.
- Prefixos comuns nesse schema: CD_ = código, DT_ = data, NM_ = nome, VL_ = valor, \
QT_ = quantidade, FL_/IN_ = flag, TP_ = tipo, DS_ = descrição.
- Quando a amostra não bastar para decidir, descreva o que dá para afirmar e diga \
que o uso exato não ficou claro. Não invente semântica.
- Descreva TODAS as colunas que receber, na ordem em que aparecem.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois e sem cerca de \
código, exatamente neste formato:

{"rotulo": "no máximo 5 palavras, serve de legenda em listagem",
 "resumo": "o que a tabela guarda, 1-3 frases",
 "funcao": "que papel ela cumpre no sistema e quando é usada, 2-4 frases",
 "dominio": "clínico | financeiro | administrativo | técnico",
 "dependencias": [{"tabela": "NOME", "motivo": "por que esta tabela precisa daquela"}],
 "dependentes": [{"tabela": "NOME", "motivo": "para que aquela tabela usa esta"}],
 "campos": [{"coluna": "NOME_DA_COLUNA", "descricao": "o que o campo guarda"}]}

"rotulo" é uma legenda curta, não uma frase: "Admissões de pacientes", \
"Catálogo de códigos". Sem artigo inicial, sem ponto final, no máximo 5 palavras.

"campos" precisa ter uma entrada para CADA coluna recebida, na mesma ordem.

Em "dependencias" e "dependentes" use SOMENTE tabelas das listas de chaves \
estrangeiras que você recebeu -- elas vêm do banco e são fato. Nunca invente um \
nome de tabela. O que você acrescenta é o MOTIVO em termos de negócio, não a lista."""


class Campo(BaseModel):
    coluna: str
    descricao: str


class Vinculo(BaseModel):
    tabela: str
    motivo: str


class Descricao(BaseModel):
    rotulo: str
    resumo: str
    funcao: str
    dominio: str
    dependencias: list[Vinculo]
    dependentes: list[Vinculo]
    campos: list[Campo]


class GeracaoFalhou(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


class RespostaVazia(GeracaoFalhou):
    """Resposta so com bloco de raciocinio, sem texto -- e transitorio.

    Medido no deepseek-v4-flash: a mesma tabela que falhou num lote respondeu
    normalmente nas duas tentativas seguintes. Vale repetir; truncagem e chave
    recusada, nao -- essas se repetem igual e so gastariam de novo.
    """


# --------------------------------------------------------------------------
# Montagem do prompt
# --------------------------------------------------------------------------

SQL_COLUNAS = """
SELECT c.nome, c.tipo_completo, c.aceita_nulo, c.eh_pk, c.comentario
  FROM catalogo.coluna c
 WHERE c.objeto_id = %s
 ORDER BY c.posicao
"""

SQL_FKS = """
SELECT array_to_string(origem_colunas, ',') AS colunas,
       destino_tabela,
       array_to_string(destino_colunas, ',') AS destino_colunas
  FROM catalogo.relacionamento WHERE origem_tabela = %s
 ORDER BY constraint_nome
"""

SQL_FKS_ENTRANDO = """
SELECT origem_tabela,
       array_to_string(origem_colunas, ',')  AS colunas,
       array_to_string(destino_colunas, ',') AS destino_colunas
  FROM catalogo.relacionamento WHERE destino_tabela = %s
 ORDER BY origem_tabela
"""

SQL_AMOSTRA = "SELECT dados FROM catalogo.amostra WHERE objeto_id = %s ORDER BY linha"

# Um hub como GLBENTERPRISE tem 39 dependentes; listar todos incha o prompt sem
# ganho, porque a IA so precisa da amostra do padrao para explicar o papel.
TETO_DEPENDENTES = 25


def amostra_orcada(linhas, teto):
    """Linhas da amostra que cabem em `teto` bytes.

    Sem piso de linhas: numa tabela de 300 colunas, forcar tres linhas e
    exatamente o que estourava o orcamento. Zero linha e um resultado valido --
    o prompt avisa que a amostra nao coube.

    `teto` e sempre explicito: um default amarrado a constante do modulo fica
    congelado na definicao da funcao e ignora qualquer ajuste posterior.
    """
    textos, gasto = [], 0
    for linha in linhas:
        texto = json.dumps(linha["dados"], ensure_ascii=False, default=str)
        if gasto + len(texto) > teto:
            break
        textos.append(texto)
        gasto += len(texto)
    return textos, len(textos)


def montar_payload(objeto):
    """Texto do prompt, quantas linhas de amostra couberam e quantas colunas."""
    colunas = catalogo.consultar(SQL_COLUNAS, (objeto["id"],), "colunas para o prompt")
    fks = catalogo.consultar(SQL_FKS, (objeto["nome"],), "FKs saindo para o prompt")
    entrando = catalogo.consultar(
        SQL_FKS_ENTRANDO, (objeto["nome"],), "FKs entrando para o prompt"
    )
    amostra = catalogo.consultar(SQL_AMOSTRA, (objeto["id"],), "amostra para o prompt")

    destino = {fk["colunas"]: f"{fk['destino_tabela']}.{fk['destino_colunas']}" for fk in fks}

    partes = [f"Tabela: {objeto['nome']}"]
    if objeto.get("comentario"):
        partes.append(f"Comentário na origem: {objeto['comentario']}")
    if objeto.get("num_registros") is not None:
        partes.append(f"Registros (estatística do Oracle): {objeto['num_registros']}")
    partes.append("")
    partes.append("Colunas:")
    for coluna in colunas:
        marcas = []
        if coluna["eh_pk"]:
            marcas.append("PK")
        if not coluna["aceita_nulo"]:
            marcas.append("NOT NULL")
        if coluna["nome"] in destino:
            marcas.append(f"FK -> {destino[coluna['nome']]}")
        if coluna["comentario"]:
            marcas.append(f'comentário: "{coluna["comentario"]}"')
        sufixo = f"  [{'; '.join(marcas)}]" if marcas else ""
        partes.append(f"  {coluna['nome']}  {coluna['tipo_completo']}{sufixo}")

    if fks:
        partes.append("")
        partes.append("Esta tabela aponta para (dependências):")
        for fk in fks:
            partes.append(
                f"  {fk['colunas']} -> {fk['destino_tabela']}.{fk['destino_colunas']}"
            )

    if entrando:
        partes.append("")
        mostrados = entrando[:TETO_DEPENDENTES]
        cabecalho = f"Tabelas que apontam para esta ({len(entrando)} no total"
        cortou = len(mostrados) < len(entrando)
        cabecalho += f", listando {len(mostrados)}):" if cortou else "):"
        partes.append(cabecalho)
        for fk in mostrados:
            partes.append(
                f"  {fk['origem_tabela']}.{fk['colunas']} -> {fk['destino_colunas']}"
            )

    # O que sobrou do teto depois do metadado obrigatorio e o que a amostra pode usar
    gasto = sum(len(parte) + 1 for parte in partes)
    linhas, quantas = amostra_orcada(amostra, max(0, TETO_PROMPT_BYTES - gasto))

    partes.append("")
    if linhas:
        partes.append(f"Amostra ({quantas} de {len(amostra)} linhas coletadas):")
        partes.extend(f"  {linha}" for linha in linhas)
    elif not amostra:
        partes.append("Sem amostra: a tabela estava vazia na extração.")
    else:
        partes.append(
            f"Amostra omitida: a tabela tem {len(colunas)} colunas e as linhas não "
            "couberam no orçamento. Descreva os campos pelo nome, tipo e chaves."
        )

    return "\n".join(partes), quantas, len(colunas)


# --------------------------------------------------------------------------
# Adaptadores por protocolo
# --------------------------------------------------------------------------


def _esquema_estrito(modelo=None):
    """JSON Schema do modelo com additionalProperties:false em todo objeto.

    O strict mode do protocolo openai exige isso; o Pydantic nao emite sozinho.
    """
    esquema = (modelo or Descricao).model_json_schema()

    def fechar(no):
        if isinstance(no, dict):
            if no.get("type") == "object":
                no["additionalProperties"] = False
                no["required"] = list(no.get("properties", {}))
            for valor in no.values():
                fechar(valor)
        elif isinstance(no, list):
            for item in no:
                fechar(item)

    fechar(esquema)
    return esquema


def _extrair_json(texto):
    """Tira cerca de codigo e qualquer texto fora do objeto JSON."""
    texto = (texto or "").strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", texto)
    inicio, fim = texto.find("{"), texto.rfind("}")
    return texto[inicio : fim + 1] if inicio != -1 and fim > inicio else texto


def _conferir_resposta(texto, truncou, blocos, prov, n_colunas):
    """Erros que precisam ser distinguidos ANTES de tentar validar o JSON.

    Truncagem chegava aqui disfarcada de "formato errado": o modelo raciocinante
    gasta o orcamento inteiro de saida e devolve so blocos de thinking, sem texto.
    """
    if truncou and not texto.strip():
        raise GeracaoFalhou(
            f"'{prov.slug}' gastou todo o orçamento de saída raciocinando",
            f"O modelo {prov.modelo} consumiu os {MAX_TOKENS_COMPATIVEL:,} tokens de "
            "saída em "
            f"raciocínio e não chegou a responder. A tabela tem {n_colunas} colunas — "
            "tente um modelo sem raciocínio estendido.".replace(",", "."),
        )
    if truncou:
        raise GeracaoFalhou(
            "A resposta não coube no limite de tokens",
            f"A tabela tem {n_colunas} colunas e a resposta foi cortada no limite "
            "de tokens de saída.",
        )
    if not texto.strip():
        tipos = ", ".join(sorted({b.get("tipo", "?") for b in blocos})) or "nenhum"
        raise RespostaVazia(
            f"'{prov.slug}' respondeu sem nenhum texto",
            f"A resposta veio só com blocos do tipo: {tipos}.",
        )


def _validar(texto, prov, modelo=None):
    try:
        return (modelo or Descricao).model_validate_json(_extrair_json(texto))
    except ValidationError as e:
        raise GeracaoFalhou(
            f"'{prov.slug}' não respondeu no formato pedido",
            "O endpoint devolveu texto livre em vez do JSON pedido. Endpoint "
            "compatível costuma ignorar saída estruturada; tente outro modelo. "
            f"Começo da resposta: {(texto or '')[:160]}",
        ) from e


def _chamar_anthropic(prov, payload, n_colunas, instrucoes=None, modelo=None,
                      esquema_nome="descricao_tabela"):
    import anthropic

    cliente = anthropic.Anthropic(api_key=prov.chave, base_url=prov.url or None)
    nativo = not prov.url
    comum = dict(
        model=prov.modelo,
        max_tokens=MAX_TOKENS if nativo else MAX_TOKENS_COMPATIVEL,
        system=[
            {
                "type": "text",
                "text": instrucoes or INSTRUCOES,
                # Cacheado: o bloco de sistema e identico em todas as chamadas de
                # um lote, e um lote de mascara sao 455 delas.
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": payload}],
    )
    # output_format e saida estruturada NATIVA da Anthropic. Endpoint compativel
    # (DeepSeek, proxies) aceita o wire format da Messages API mas ignora esse
    # parametro e responde em prosa -- foi o que quebrou aqui. Com base_url
    # proprio pedimos o JSON no prompt e validamos, como o adaptador openai ja faz.
    try:
        if nativo:
            resposta = cliente.messages.parse(
                **comum, thinking={"type": "adaptive"}, output_format=modelo or Descricao
            )
            descricao = resposta.parsed_output
        else:
            with cliente.messages.stream(**comum) as fluxo:
                resposta = fluxo.get_final_message()
            texto = "".join(b.text for b in resposta.content if b.type == "text")
            _conferir_resposta(
                texto,
                resposta.stop_reason == "max_tokens",
                [{"tipo": b.type} for b in resposta.content],
                prov,
                n_colunas,
            )
            descricao = _validar(texto, prov, modelo)
    except ValidationError as e:
        # parse() valida dentro do SDK e nao devolve o texto cru para inspecao
        raise GeracaoFalhou(
            f"'{prov.slug}' não respondeu no formato pedido",
            f"A resposta não era o JSON esperado. Detalhe: {e}",
        ) from e
    except anthropic.AuthenticationError as e:
        raise GeracaoFalhou(f"A chave de '{prov.slug}' foi recusada", str(e)) from e
    except anthropic.RateLimitError as e:
        raise GeracaoFalhou("Limite de requisições atingido, tente de novo", str(e)) from e
    except anthropic.APIConnectionError as e:
        raise GeracaoFalhou(f"Não conseguimos alcançar '{prov.slug}'", str(e)) from e
    except anthropic.APIStatusError as e:
        raise GeracaoFalhou(f"'{prov.slug}' respondeu {e.status_code}", str(e)) from e

    return (
        descricao,
        resposta.stop_reason == "max_tokens",
        resposta.usage.input_tokens,
        resposta.usage.output_tokens,
    )


def _chamar_openai(prov, payload, n_colunas, instrucoes=None, modelo=None,
                   esquema_nome="descricao_tabela"):
    """Wire format cru (response_format json_schema), nao o helper .parse() do SDK.

    E o que endpoint compativel (Ollama, Groq, OpenRouter, vLLM) tambem entende --
    e um deles e justamente o motivo de existir o IA_<NOME>_URL.
    """
    import openai

    cliente = openai.OpenAI(api_key=prov.chave, base_url=prov.url or None)
    corpo = dict(
        model=prov.modelo,
        messages=[
            {"role": "system", "content": instrucoes or INSTRUCOES},
            {"role": "user", "content": payload},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": esquema_nome,
                "strict": True,
                "schema": _esquema_estrito(modelo),
            },
        },
    )

    try:
        # Modelo novo da OpenAI recusa max_tokens e exige max_completion_tokens;
        # endpoint compativel costuma aceitar so o antigo. Tenta os dois.
        try:
            resposta = cliente.chat.completions.create(max_tokens=MAX_TOKENS, **corpo)
        except openai.BadRequestError as e:
            if "max_completion_tokens" not in str(e):
                raise
            resposta = cliente.chat.completions.create(
                max_completion_tokens=MAX_TOKENS, **corpo
            )
    except openai.AuthenticationError as e:
        raise GeracaoFalhou(f"A chave de '{prov.slug}' foi recusada", str(e)) from e
    except openai.RateLimitError as e:
        raise GeracaoFalhou("Limite de requisições atingido, tente de novo", str(e)) from e
    except openai.APIConnectionError as e:
        raise GeracaoFalhou(f"Não conseguimos alcançar '{prov.slug}'", str(e)) from e
    except openai.APIStatusError as e:
        raise GeracaoFalhou(f"'{prov.slug}' respondeu {e.status_code}", str(e)) from e

    escolha = resposta.choices[0]
    _conferir_resposta(
        escolha.message.content or "",
        escolha.finish_reason == "length",
        [{"tipo": "message"}],
        prov,
        n_colunas,
    )
    descricao = _validar(escolha.message.content, prov, modelo)

    uso = resposta.usage
    return (
        descricao,
        escolha.finish_reason == "length",
        getattr(uso, "prompt_tokens", None),
        getattr(uso, "completion_tokens", None),
    )


ADAPTADORES = {"anthropic": _chamar_anthropic, "openai": _chamar_openai}


# --------------------------------------------------------------------------
# Entrada usada pela rota
# --------------------------------------------------------------------------


def aterrar(descricao, objeto):
    """Descarta vinculo cujo nome de tabela nao esta nas FKs reais do catalogo.

    A lista de tabelas e fato do banco; a IA so acrescenta o motivo. Num catalogo
    de dados, uma dependencia inventada e pior do que uma faltando.
    """
    reais = {
        "dependencias": {
            linha["destino_tabela"]
            for linha in catalogo.consultar(
                SQL_FKS, (objeto["nome"],), "FKs para conferência"
            )
        },
        "dependentes": {
            linha["origem_tabela"]
            for linha in catalogo.consultar(
                SQL_FKS_ENTRANDO, (objeto["nome"],), "FKs para conferência"
            )
        },
    }
    for campo, nomes in reais.items():
        vinculos = getattr(descricao, campo)
        mantidos = [v for v in vinculos if v.tabela in nomes]
        if len(mantidos) != len(vinculos):
            inventados = [v.tabela for v in vinculos if v.tabela not in nomes]
            logger.warning(
                "%s: descartando %s de '%s' fora das FKs reais: %s",
                objeto["nome"],
                len(inventados),
                campo,
                ", ".join(inventados),
            )
        setattr(descricao, campo, mantidos)
    return descricao


def descrever(objeto, par=None):
    """Chama a API e devolve (Descricao, metadados).

    `par` e o "slug::modelo" escolhido na pagina; sem ele usa o primeiro ativo.
    """
    prov = provedores.escolher(par)
    payload, linhas_prompt, n_colunas = montar_payload(objeto)

    logger.info(
        "descrevendo %s via %s (%s/%s): %s colunas, %s linhas de amostra, %s bytes",
        objeto["nome"],
        prov.slug,
        prov.tipo,
        prov.modelo,
        n_colunas,
        linhas_prompt,
        len(payload),
    )

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            descricao, truncou, entrada, saida = ADAPTADORES[prov.tipo](
                prov, payload, n_colunas
            )
            break
        except RespostaVazia as vazia:
            if tentativa == TENTATIVAS:
                raise
            logger.warning(
                "%s: %s na tentativa %s de %s, repetindo",
                objeto["nome"],
                vazia.motivo,
                tentativa,
                TENTATIVAS,
            )

    # Numa tabela muito larga a resposta pode bater o teto: melhor falhar do que
    # gravar uma lista de campos pela metade fingindo que esta completa
    if truncou:
        raise GeracaoFalhou(
            "A resposta não coube no limite de tokens",
            f"{objeto['nome']} tem {n_colunas} colunas. Use um modelo com saída maior "
            "ou descreva a tabela em partes.",
        )

    aterrar(descricao, objeto)

    meta = {
        "provedor": prov.slug,
        "modelo": prov.modelo,
        "colunas_descritas": len(descricao.campos),
        "linhas_no_prompt": linhas_prompt,
        "tokens_entrada": entrada,
        "tokens_saida": saida,
    }
    return descricao, meta


SQL_GRAVAR = """
INSERT INTO catalogo.descricao_ia
    (objeto_id, rotulo, resumo, funcao, dominio, dependencias, dependentes, campos,
     provedor, modelo, gerado_em,
     colunas_descritas, linhas_no_prompt, tokens_entrada, tokens_saida)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s)
ON CONFLICT (objeto_id) DO UPDATE SET
    rotulo            = EXCLUDED.rotulo,
    resumo            = EXCLUDED.resumo,
    funcao            = EXCLUDED.funcao,
    dominio           = EXCLUDED.dominio,
    dependencias      = EXCLUDED.dependencias,
    dependentes       = EXCLUDED.dependentes,
    campos            = EXCLUDED.campos,
    provedor          = EXCLUDED.provedor,
    modelo            = EXCLUDED.modelo,
    gerado_em         = now(),
    colunas_descritas = EXCLUDED.colunas_descritas,
    linhas_no_prompt  = EXCLUDED.linhas_no_prompt,
    tokens_entrada    = EXCLUDED.tokens_entrada,
    tokens_saida      = EXCLUDED.tokens_saida
"""


def _lista(itens):
    return json.dumps([item.model_dump() for item in itens], ensure_ascii=False)


def gravar(objeto, descricao, meta):
    catalogo.executar(
        SQL_GRAVAR,
        (
            objeto["id"],
            descricao.rotulo,
            descricao.resumo,
            descricao.funcao,
            descricao.dominio,
            _lista(descricao.dependencias),
            _lista(descricao.dependentes),
            _lista(descricao.campos),
            meta["provedor"],
            meta["modelo"],
            meta["colunas_descritas"],
            meta["linhas_no_prompt"],
            meta["tokens_entrada"],
            meta["tokens_saida"],
        ),
        f"descrição de {objeto['nome']}",
    )


# --------------------------------------------------------------------------
# Classificacao de sensibilidade, coluna a coluna
#
# Sucessora do mascaramento por substring que saiu da extracao. Aquele decidia
# pelo NOME da coluna e errava dos dois lados -- "RG" casava CD_ORGAO, e numero
# nunca era mascarado, entao CPF gravado como NUMBER passava inteiro. Aqui quem
# julga e o modelo, com a descricao que ja foi gerada para o campo e o nome da
# tabela em volta: e o contexto que separa NAME em GLBPERSON de NAME em
# GLBPROCEDURE.
#
# O veredito e INVENTARIO. Nada e ocultado por causa dele -- nem a amostra na
# tela, nem o prompt da descricao.
# --------------------------------------------------------------------------

CATEGORIAS = (
    "nome", "documento", "contato", "endereco",
    "clinico", "credencial", "financeiro", "nenhuma",
)

# Colunas por chamada. E o teto de contagem; COLUNAS_TETO_BYTES corta antes
# quando as descricoes vem longas.
#
# 50, e nao 100, porque o raciocinio do modelo cresce muito mais rapido que o
# pacote. Medido no deepseek-v4-flash, com o mesmo catalogo:
#
#     25 colunas ->  19,8s,  3.020 tokens de saida  (121 por coluna)
#     50 colunas ->  34,1s,  5.157 tokens de saida  (103 por coluna)
#    100 colunas -> 188,3s, 26.071 tokens de saida  (261 por coluna)
#
# Dobrar de 50 para 100 multiplica a saida por cinco. Nas 45 mil colunas isso e a
# diferenca entre 4,7 milhoes de tokens em ~2h e 11,9 milhoes em ~6h. Subir este
# numero parece economizar chamadas e sai mais caro -- remedir antes de mexer.
COLUNAS_POR_PACOTE = 50

# Teto do payload de um pacote. Medido neste catalogo, 100 colunas dao ~11 KB
# (p95 13 KB). O numero e prudente e vem da medicao do topo deste modulo: com
# 32.796 bytes o modelo gastou a saida inteira raciocinando e devolveu texto
# nenhum. Estourar aqui e mandar menos colunas, nao arriscar a chamada.
COLUNAS_TETO_BYTES = 24_000

INSTRUCOES_MASCARA = """Você classifica colunas de um schema Oracle legado de um \
sistema de saúde (geriatria, internação domiciliar) quanto a conterem dado sensível.

Recebe uma lista de colunas, cada uma com um id, a tabela a que pertence, o nome, o \
tipo e a descrição do que ela guarda. Devolva um veredito para CADA id recebido.

Sensível é a coluna cujo VALOR identifica uma pessoa ou revela algo sobre ela:
- nome        — nome de paciente, responsável, profissional, contato
- documento   — CPF, RG, CNS, passaporte, cartão do convênio, matrícula pessoal
- contato     — telefone, celular, e-mail
- endereco    — logradouro, bairro, CEP, coordenada de residência
- clinico     — diagnóstico, evolução, queixa, prescrição, resultado de exame, \
qualquer texto livre escrito sobre o paciente
- credencial  — senha, hash, token, chave de API, string de conexão
- financeiro  — conta bancária, cartão, dado de pagamento identificável
- nenhuma     — quando NÃO for sensível

Regras que decidem os casos difíceis:
- Julgue pelo CONTEÚDO, não pelo nome. Um campo chamado CD_ORGAO guarda o código de \
um setor, não um RG; um campo chamado NAME guarda nome de pessoa numa tabela de \
pacientes e nome de procedimento numa tabela de procedimentos. A tabela é o que \
desempata — use-a.
- Chave estrangeira e identificador interno NÃO são sensíveis. IDPATIENT aponta para \
o paciente, mas o número em si não diz nada sobre ninguém.
- Data isolada de evento operacional não é sensível; data de nascimento é.
- Texto livre que um profissional escreve sobre o paciente é sensível, mesmo que a \
descrição não diga "diagnóstico" com todas as letras.
- Na dúvida entre sensível e não sensível, marque como sensível e explique a dúvida \
no motivo. Um falso positivo se revisa; um falso negativo vaza.
- motivo: uma frase curta dizendo o que decidiu. Quando não for sensível, diga o que \
a coluna guarda de fato.
- categoria é "nenhuma" quando, e somente quando, sensivel for false.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois e sem cerca de \
código, exatamente neste formato:

{"colunas": [{"id": 123, "sensivel": true, "categoria": "clinico",
              "motivo": "uma frase curta dizendo o que decidiu"}]}

"colunas" precisa ter uma entrada para CADA id recebido, e o "id" tem de ser \
copiado do que veio na linha. Não invente id, não omita nenhum, não repita.
"""


class VereditoColuna(BaseModel):
    id: int
    sensivel: bool
    categoria: str
    motivo: str


class Classificacao(BaseModel):
    colunas: list[VereditoColuna]


def empacotar_colunas(colunas, teto=COLUNAS_POR_PACOTE, teto_bytes=COLUNAS_TETO_BYTES):
    """Fatia as colunas em pacotes, por contagem E por bytes.

    Cortar so pela contagem seria confiar que 100 descricoes cabem sempre; elas
    variam, e prompt grande demais neste modelo nao devolve resposta pior -- nao
    devolve resposta nenhuma. Uma coluna sozinha maior que o teto vai sozinha, em
    vez de virar um pacote vazio e travar o lote.
    """
    pacotes, atual, bytes_atuais = [], [], 0
    for coluna in colunas:
        tamanho = len(_linha_da_coluna(coluna)) + 1
        if atual and (len(atual) >= teto or bytes_atuais + tamanho > teto_bytes):
            pacotes.append(atual)
            atual, bytes_atuais = [], 0
        atual.append(coluna)
        bytes_atuais += tamanho
    if atual:
        pacotes.append(atual)
    return pacotes


def _linha_da_coluna(coluna):
    return (
        f"{coluna['id']} | {coluna['objeto']}.{coluna['nome']} "
        f"({coluna['tipo_completo']}) | {coluna.get('descricao_ia') or ''}"
    )


def montar_payload_mascara(pacote):
    partes = ["id | tabela.coluna (tipo) | descrição", ""]
    partes.extend(_linha_da_coluna(coluna) for coluna in pacote)
    return "\n".join(partes)


def conferir_vereditos(pacote, classificacao):
    """Casa cada veredito com a coluna que o pediu. Devolve a lista pronta.

    O modelo devolve um array e nada garante a ordem nem a completude. Casar por
    POSICAO gravaria, numa resposta com 87 de 100 itens, o veredito da vizinha em
    cada coluna -- e ninguem veria. Por isso cada coluna leva o seu id e o
    conjunto devolvido tem de ser exatamente igual ao enviado.
    """
    pedidos = {coluna["id"] for coluna in pacote}
    devolvidos = [v.id for v in classificacao.colunas]
    if len(set(devolvidos)) != len(devolvidos):
        raise GeracaoFalhou(
            "O modelo repetiu colunas na resposta",
            f"{len(devolvidos)} vereditos para {len(pedidos)} colunas pedidas.",
        )
    if set(devolvidos) != pedidos:
        faltando = sorted(pedidos - set(devolvidos))[:5]
        sobrando = sorted(set(devolvidos) - pedidos)[:5]
        raise GeracaoFalhou(
            "O modelo não devolveu um veredito por coluna",
            f"pedidas {len(pedidos)}, devolvidas {len(set(devolvidos))}. "
            f"Faltando: {faltando or 'nenhuma'}. Desconhecidas: {sobrando or 'nenhuma'}.",
        )

    fora = {v.categoria for v in classificacao.colunas} - set(CATEGORIAS)
    if fora:
        raise GeracaoFalhou(
            "O modelo usou categoria fora da lista",
            f"Categorias desconhecidas: {sorted(fora)}.",
        )
    return classificacao.colunas


def classificar(pacote, par=None):
    """Um pacote de colunas -> (vereditos, meta). Uma chamada paga."""
    prov = provedores.escolher(par)
    payload = montar_payload_mascara(pacote)

    classificacao, truncou, entrada, saida = _chamar_com_retentativa(
        prov, payload, len(pacote),
        instrucoes=INSTRUCOES_MASCARA,
        modelo=Classificacao,
        esquema_nome="classificacao_colunas",
    )
    if truncou:
        raise GeracaoFalhou(
            f"'{prov.slug}' truncou a resposta",
            f"O pacote tinha {len(pacote)} colunas. Reduza ia.COLUNAS_POR_PACOTE.",
        )

    vereditos = conferir_vereditos(pacote, classificacao)
    meta = {
        "provedor": prov.slug,
        "modelo": prov.modelo,
        "colunas": len(vereditos),
        "tokens_entrada": entrada,
        "tokens_saida": saida,
    }
    return vereditos, meta


def _chamar_com_retentativa(prov, payload, n_itens, **extras):
    """Chama o adaptador repetindo o que e transitorio. Devolve o que ele devolve.

    Repete em resposta vazia, como descrever() ja fazia, E em limite de
    requisicao -- que descrever() nao trata. Um lote de descricao sao ~2 mil
    chamadas espalhadas por minutos de geracao cada; um lote de mascara sao
    centenas de chamadas curtas em rajada, e ai o 429 deixa de ser hipotese.
    A espera e exponencial com jitter, no molde de embeddings._um_lote.
    """
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            return ADAPTADORES[prov.tipo](prov, payload, n_itens, **extras)
        except (RespostaVazia, GeracaoFalhou) as falha:
            transitoria = isinstance(falha, RespostaVazia) or "Limite de requisições" in falha.motivo
            if not transitoria or tentativa == TENTATIVAS:
                raise
            espera = ESPERA_BASE**tentativa + random.uniform(0, 1)
            logger.warning(
                "%s na tentativa %s de %s, repetindo em %.1fs",
                falha.motivo, tentativa, TENTATIVAS, espera,
            )
            time.sleep(espera)


SQL_GRAVAR_MASCARA = """
UPDATE catalogo.coluna c
   SET sensivel = v.sensivel, sensivel_categoria = v.categoria,
       sensivel_motivo = v.motivo, sensivel_modelo = %s, sensivel_em = now()
  FROM (SELECT unnest(%s::bigint[])  AS id,
               unnest(%s::boolean[]) AS sensivel,
               unnest(%s::text[])    AS categoria,
               unnest(%s::text[])    AS motivo) v
 WHERE c.id = v.id
"""


def gravar_mascara(vereditos, meta):
    """Um UPDATE para o pacote inteiro.

    catalogo.executar abre uma conexao por chamada -- gravar coluna a coluna
    seriam 100 conexoes por pacote, 45 mil no lote.
    """
    catalogo.executar(
        SQL_GRAVAR_MASCARA,
        (
            meta["modelo"],
            [v.id for v in vereditos],
            [v.sensivel for v in vereditos],
            [v.categoria for v in vereditos],
            [v.motivo for v in vereditos],
        ),
        f"classificação de {len(vereditos)} colunas",
    )
