"""Comparacao entre tabelas do catalogo: Oracle > Comparar.

Duas camadas, de proposito separadas:

- a DIFERENCA ESTRUTURAL (diferenca()), calculada na hora a partir do catalogo:
  e fato, de graca e sempre atual;
- a ANALISE POR IA, que le essa diferenca + as descricoes ja geradas + um pouco
  de amostra e diz o que muda em termos de negocio. Paga, entao fica gravada em
  catalogo.comparacao_ia, uma por conjunto de objetos.

O caso tipico e a mesma tabela em varios schemas (CAPPAYMENT em dois ambientes do
ERP), mas o conjunto e livre: qualquer 2 a 6 objetos de qualquer schema.

A amostra que vai no prompt e o dado real da origem, como na descricao da tabela
(src/ia.py).
"""

import json
import logging

from pydantic import BaseModel

from . import catalogo, ia, provedores

logger = logging.getLogger(__name__)

MINIMO = 2
MAXIMO = 6
LIMITE_BUSCA = 50


class ComparacaoInvalida(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


# --------------------------------------------------------------------------
# Selecao
# --------------------------------------------------------------------------

COLUNAS_OBJETO = """
o.id, o.nome, o.tipo, o.num_registros, o.atualizado_em, o.esquema_id,
e.nome AS esquema, s.nome AS servidor
"""
ORIGEM_OBJETO = """
catalogo.objeto o
JOIN catalogo.esquema e ON e.id = o.esquema_id
JOIN catalogo.servidor s ON s.id = e.servidor_id
"""


def ids_validos(valores):
    """Lista de ids (texto, int ou "1,2,3") -> ids unicos na ordem dada.

    Recusa menos de MINIMO e mais de MAXIMO: com uma tabela nao ha o que
    comparar, e acima de seis a matriz e o prompt deixam de caber.
    """
    if isinstance(valores, (str, int)):
        valores = [valores]
    ids = []
    for valor in valores:
        for parte in str(valor).split(","):
            parte = parte.strip()
            if not parte:
                continue
            try:
                numero = int(parte)
            except ValueError as e:
                raise ComparacaoInvalida(f"Identificador inválido: {parte}") from e
            if numero not in ids:
                ids.append(numero)
    if len(ids) < MINIMO:
        raise ComparacaoInvalida(
            "Escolha ao menos duas tabelas", "Com uma tabela só não há o que comparar."
        )
    if len(ids) > MAXIMO:
        raise ComparacaoInvalida(
            f"Escolha no máximo {MAXIMO} tabelas",
            "Acima disso a matriz e o prompt da IA deixam de caber.",
        )
    return ids


def assinatura(ids):
    """O mesmo conjunto em outra ordem e a mesma comparacao."""
    return ",".join(str(i) for i in sorted(ids))


def candidatos(nome):
    """O objeto de mesmo nome em todos os schemas do catalogo."""
    return catalogo.consultar(
        f"SELECT {COLUNAS_OBJETO} FROM {ORIGEM_OBJETO} WHERE upper(o.nome) = upper(%s) "
        "ORDER BY s.nome, e.nome",
        (nome.strip(),), "candidatos da comparação",
    )


def buscar(termo):
    """Objetos de qualquer schema pelo nome -- a comparacao livre."""
    return catalogo.consultar(
        f"SELECT {COLUNAS_OBJETO} FROM {ORIGEM_OBJETO} WHERE o.nome ILIKE %s "
        f"ORDER BY o.nome, s.nome, e.nome LIMIT {LIMITE_BUSCA}",
        (f"%{termo.strip()}%",), "busca da comparação",
    )


def resumo_objetos(ids):
    """Metadado curto de cada id, na ordem pedida; id que sumiu fica de fora."""
    if not ids:
        return []
    linhas = catalogo.consultar(
        f"SELECT {COLUNAS_OBJETO} FROM {ORIGEM_OBJETO} WHERE o.id = ANY(%s)",
        (list(ids),), "objetos da comparação",
    )
    por_id = {linha["id"]: linha for linha in linhas}
    return [por_id[i] for i in ids if i in por_id]


def rotular(objetos):
    """SCHEMA.NOME de cada objeto; com o servidor na frente quando dois schemas
    de servidores diferentes tem o mesmo nome."""
    simples = [f"{o['esquema']}.{o['nome']}" for o in objetos]
    repetidos = {r for r in simples if simples.count(r) > 1}
    for objeto, rotulo in zip(objetos, simples):
        objeto["rotulo"] = (
            f"{objeto['servidor']}/{rotulo}" if rotulo in repetidos else rotulo
        )
    return objetos


# --------------------------------------------------------------------------
# Carga
# --------------------------------------------------------------------------

SQL_COLUNAS = """
SELECT nome, tipo_completo, aceita_nulo, eh_pk, comentario, descricao_ia, sempre_nulo
  FROM catalogo.coluna WHERE objeto_id = %s ORDER BY posicao
"""
SQL_INDICES = "SELECT nome, unico, colunas FROM catalogo.indice WHERE objeto_id = %s ORDER BY nome"
SQL_DESCRICAO = "SELECT rotulo, resumo, funcao FROM catalogo.descricao_ia WHERE objeto_id = %s"


def carregar(ids):
    """Tudo que a diferenca e o prompt precisam, objeto a objeto."""
    objetos = resumo_objetos(ids)
    faltando = set(ids) - {o["id"] for o in objetos}
    if faltando:
        raise ComparacaoInvalida(
            "Uma das tabelas não está mais no catálogo",
            f"Ids sem objeto: {', '.join(str(i) for i in sorted(faltando))}.",
        )
    for objeto in objetos:
        objeto["colunas"] = catalogo.consultar(
            SQL_COLUNAS, (objeto["id"],), f"colunas de {objeto['nome']}"
        )
        objeto["fks"] = catalogo.consultar(
            ia.SQL_FKS, (objeto["nome"], objeto["esquema_id"]), f"FKs de {objeto['nome']}"
        )
        objeto["indices"] = catalogo.consultar(
            SQL_INDICES, (objeto["id"],), f"índices de {objeto['nome']}"
        )
        objeto["descricao"] = catalogo.um(
            SQL_DESCRICAO, (objeto["id"],), f"descrição de {objeto['nome']}"
        )
        objeto["amostra"] = catalogo.consultar(
            ia.SQL_AMOSTRA, (objeto["id"],), f"amostra de {objeto['nome']}"
        )
    return rotular(objetos)


# --------------------------------------------------------------------------
# Diferenca estrutural (pura)
# --------------------------------------------------------------------------


def _estado(coluna):
    return {"tipo": coluna["tipo_completo"], "nulo": coluna["aceita_nulo"], "pk": coluna["eh_pk"]}


def _classe(estados):
    if any(e is None for e in estados):
        return "ausente"
    for chave in ("tipo", "nulo", "pk"):
        if len({e[chave] for e in estados}) > 1:
            return chave
    return "igual"


def _presencas(objetos, chaves_por_objeto):
    """União das chaves, na ordem de aparicao, com a presenca em cada objeto."""
    ordem = []
    for chaves in chaves_por_objeto:
        for chave in chaves:
            if chave not in ordem:
                ordem.append(chave)
    return [
        {"chave": chave,
         "presente": [chave in chaves for chaves in chaves_por_objeto],
         "classe": "igual" if all(chave in c for c in chaves_por_objeto) else "ausente"}
        for chave in ordem
    ]


def diferenca(objetos):
    """Matriz de colunas, FKs e indices entre os objetos.

    Coluna: a classe e a PRIMEIRA divergencia encontrada, nesta ordem: ausente
    em alguma tabela, tipo, nulidade, PK. "igual" so quando as tres batem em
    todas.
    """
    por_objeto = [{c["nome"]: c for c in o["colunas"]} for o in objetos]
    ordem = []
    for o in objetos:
        for coluna in o["colunas"]:
            if coluna["nome"] not in ordem:
                ordem.append(coluna["nome"])

    linhas = []
    for nome in ordem:
        estados = [_estado(cols[nome]) if nome in cols else None for cols in por_objeto]
        linhas.append({"coluna": nome, "estados": estados, "classe": _classe(estados)})

    classes = [linha["classe"] for linha in linhas]
    totais = {
        "colunas": len(linhas),
        "iguais": classes.count("igual"),
        "divergentes": sum(classes.count(c) for c in ("tipo", "nulo", "pk")),
        "ausentes": classes.count("ausente"),
        "exclusivas": [
            sum(1 for linha in linhas
                if linha["estados"][i] is not None
                and sum(e is not None for e in linha["estados"]) == 1)
            for i in range(len(objetos))
        ],
    }

    fks = _presencas(objetos, [
        [f"{fk['colunas']} -> {fk['destino_tabela']}.{fk['destino_colunas']}" for fk in o["fks"]]
        for o in objetos
    ])
    indices = _presencas(objetos, [
        [("único " if ix["unico"] else "") + "(" + ", ".join(ix["colunas"]) + ")"
         for ix in o["indices"]]
        for o in objetos
    ])
    return {"colunas": linhas, "totais": totais, "fks": fks, "indices": indices}


def texto_estado(estado):
    if estado is None:
        return "ausente"
    marcas = [estado["tipo"]]
    if not estado["nulo"]:
        marcas.append("NOT NULL")
    if estado["pk"]:
        marcas.append("PK")
    return " ".join(marcas)


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

INSTRUCOES_COMPARACAO = """Você é um analista de dados comparando tabelas de um \
schema Oracle legado de um sistema de saúde (geriatria, internação domiciliar). \
Normalmente é a MESMA tabela em ambientes ou schemas diferentes do ERP, mas pode \
ser um conjunto livre de tabelas parecidas.

Você recebe, de cada tabela: o rótulo (SCHEMA.NOME), registros, a descrição já \
gerada (quando há), a diferença estrutural calculada pelo banco e algumas linhas \
de amostra. A diferença estrutural é FATO -- não a conteste nem a repita linha a \
linha; interprete-a.

Regras:
- Escreva em português do Brasil, direto.
- Diga o que as diferenças significam: versão diferente do ERP, customização de \
um ambiente, coluna nova ainda não usada, mesmo conceito com nome diferente, \
uso diferente do mesmo campo visto na amostra.
- Use a amostra para dizer se uma coluna é de fato usada (sempre nula, valores \
de formatos diferentes) -- e diga quando a amostra não basta.
- Cite SOMENTE tabelas pelos rótulos recebidos e colunas que existem nelas. \
Nunca invente nome.
- Não invente semântica: quando não der para afirmar, diga isso.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois:

{"resumo": "2-4 frases: são a mesma entidade? o quanto divergem e por quê",
 "semelhancas": [{"aspecto": "curto", "detalhe": "1-2 frases"}],
 "diferencas": [{"aspecto": "curto", "tabelas": ["ROTULO"], "detalhe": "o que muda",
                 "impacto": "o que isso afeta para quem consulta ou integra"}],
 "equivalencias": [{"conceito": "o que representam",
                    "colunas": [{"tabela": "ROTULO", "coluna": "NOME"}]}],
 "recomendacoes": ["ação curta para quem for unificar, migrar ou consultar"]}

Em "equivalencias" ponha só colunas de NOME OU TIPO diferentes que guardam o mesmo \
conceito em tabelas distintas -- colunas iguais já aparecem na matriz."""


class Semelhanca(BaseModel):
    aspecto: str
    detalhe: str


class Diferenca(BaseModel):
    aspecto: str
    tabelas: list[str]
    detalhe: str
    impacto: str


class ColunaRef(BaseModel):
    tabela: str
    coluna: str


class Equivalencia(BaseModel):
    conceito: str
    colunas: list[ColunaRef]


class Comparacao(BaseModel):
    resumo: str
    semelhancas: list[Semelhanca]
    diferencas: list[Diferenca]
    equivalencias: list[Equivalencia]
    recomendacoes: list[str]


def montar_payload(objetos, dif, teto=None):
    """Texto do prompt e quantas linhas de amostra couberam, no total.

    Metadado primeiro e inteiro; a amostra divide o que sobrar do teto em partes
    iguais entre as tabelas, para nenhuma ficar sem e outra levar tudo.
    """
    teto = ia.TETO_PROMPT_BYTES if teto is None else teto
    partes = [f"Comparação de {len(objetos)} tabelas:"]
    for i, o in enumerate(objetos, start=1):
        partes.append(
            f"[{i}] {o['rotulo']} ({o['tipo']}) -- servidor {o['servidor']}, "
            f"registros: {o['num_registros'] if o['num_registros'] is not None else '?'}, "
            f"{len(o['colunas'])} colunas"
        )
        if o.get("descricao"):
            d = o["descricao"]
            partes.append(f"    Descrição já gerada: {d['resumo']} {d.get('funcao') or ''}".rstrip())

    iguais = [linha["coluna"] for linha in dif["colunas"] if linha["classe"] == "igual"]
    diferentes = [linha for linha in dif["colunas"] if linha["classe"] != "igual"]
    partes.append("")
    partes.append(f"Colunas idênticas em todas ({len(iguais)}): "
                  + (", ".join(iguais) if iguais else "nenhuma"))
    partes.append("")
    partes.append(f"Colunas com diferença ({len(diferentes)}):")
    for linha in diferentes:
        estados = " | ".join(
            f"[{i}] {texto_estado(e)}" for i, e in enumerate(linha["estados"], start=1)
        )
        partes.append(f"  {linha['coluna']} ({linha['classe']}): {estados}")

    for titulo, chave in (("Chaves estrangeiras", "fks"), ("Índices", "indices")):
        divergentes = [x for x in dif[chave] if x["classe"] != "igual"]
        partes.append("")
        partes.append(
            f"{titulo}: {len(dif[chave]) - len(divergentes)} iguais em todas; "
            f"{len(divergentes)} só em parte das tabelas"
            + (":" if divergentes else ".")
        )
        for x in divergentes:
            onde = ", ".join(f"[{i}]" for i, p in enumerate(x["presente"], start=1) if p)
            partes.append(f"  {x['chave']} -- só em {onde}")

    gasto = sum(len(p) + 1 for p in partes)
    por_tabela = max(0, teto - gasto) // max(1, len(objetos))
    total = 0
    partes.append("")
    partes.append("Amostras:")
    for i, o in enumerate(objetos, start=1):
        linhas, quantas = ia.amostra_orcada(o["amostra"], por_tabela)
        total += quantas
        if linhas:
            partes.append(f"[{i}] {o['rotulo']} ({quantas} de {len(o['amostra'])} linhas):")
            partes.extend(f"  {linha}" for linha in linhas)
        elif not o["amostra"]:
            partes.append(f"[{i}] {o['rotulo']}: sem amostra (vazia na extração).")
        else:
            partes.append(f"[{i}] {o['rotulo']}: amostra não coube no orçamento.")
    return "\n".join(partes), total


def aterrar(comparacao, objetos):
    """Descarta tabela e coluna citadas que nao existem no conjunto."""
    colunas = {o["rotulo"]: {c["nome"] for c in o["colunas"]} for o in objetos}
    inventados = []

    for d in comparacao.diferencas:
        validas = [t for t in d.tabelas if t in colunas]
        inventados += [t for t in d.tabelas if t not in colunas]
        d.tabelas = validas

    mantidas = []
    for eq in comparacao.equivalencias:
        refs = [r for r in eq.colunas if r.coluna in colunas.get(r.tabela, ())]
        inventados += [f"{r.tabela}.{r.coluna}" for r in eq.colunas if r not in refs]
        # Equivalencia de uma coluna so nao liga nada a nada
        if len(refs) >= 2:
            eq.colunas = refs
            mantidas.append(eq)
    comparacao.equivalencias = mantidas

    if inventados:
        logger.warning("comparação: descartando referências fora do conjunto: %s",
                       ", ".join(inventados))
    return comparacao


def gerar(objetos, dif, par=None):
    """Chama a IA e devolve (Comparacao, meta). Uma chamada paga."""
    prov = provedores.escolher(par)
    payload, linhas = montar_payload(objetos, dif)
    n_colunas = dif["totais"]["colunas"]
    logger.info("comparando %s via %s/%s: %s colunas, %s linhas de amostra, %s bytes",
                " x ".join(o["rotulo"] for o in objetos), prov.slug, prov.modelo,
                n_colunas, linhas, len(payload))

    comparacao, truncou, entrada, saida = ia._chamar_com_retentativa(
        prov, payload, n_colunas,
        instrucoes=INSTRUCOES_COMPARACAO,
        modelo=Comparacao,
        esquema_nome="comparacao_tabelas",
    )
    if truncou:
        raise ia.GeracaoFalhou(
            "A resposta não coube no limite de tokens",
            "Compare menos tabelas de uma vez ou use um modelo com saída maior.",
        )
    aterrar(comparacao, objetos)
    meta = {"provedor": prov.slug, "modelo": prov.modelo, "linhas_no_prompt": linhas,
            "tokens_entrada": entrada, "tokens_saida": saida}
    return comparacao, meta


# --------------------------------------------------------------------------
# Gravacao
# --------------------------------------------------------------------------

SQL_GRAVAR = """
INSERT INTO catalogo.comparacao_ia
    (objetos, assinatura, rotulos, resumo, semelhancas, diferencas, equivalencias,
     recomendacoes, provedor, modelo, gerado_em, gerado_por, linhas_no_prompt,
     tokens_entrada, tokens_saida)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s, %s, %s)
ON CONFLICT (assinatura) DO UPDATE SET
    objetos = EXCLUDED.objetos, rotulos = EXCLUDED.rotulos, resumo = EXCLUDED.resumo,
    semelhancas = EXCLUDED.semelhancas, diferencas = EXCLUDED.diferencas,
    equivalencias = EXCLUDED.equivalencias, recomendacoes = EXCLUDED.recomendacoes,
    provedor = EXCLUDED.provedor, modelo = EXCLUDED.modelo, gerado_em = now(),
    gerado_por = EXCLUDED.gerado_por, linhas_no_prompt = EXCLUDED.linhas_no_prompt,
    tokens_entrada = EXCLUDED.tokens_entrada, tokens_saida = EXCLUDED.tokens_saida
"""


def _json(itens):
    return json.dumps([i.model_dump() if hasattr(i, "model_dump") else i for i in itens],
                      ensure_ascii=False)


def gravar(objetos, comparacao, meta, usuario=None):
    ids = [o["id"] for o in objetos]
    catalogo.executar(
        SQL_GRAVAR,
        (ids, assinatura(ids), [o["rotulo"] for o in objetos], comparacao.resumo,
         _json(comparacao.semelhancas), _json(comparacao.diferencas),
         _json(comparacao.equivalencias), _json(comparacao.recomendacoes),
         meta["provedor"], meta["modelo"], usuario, meta["linhas_no_prompt"],
         meta["tokens_entrada"], meta["tokens_saida"]),
        "gravação da comparação",
    )


def buscar_gravada(ids):
    return catalogo.um(
        "SELECT * FROM catalogo.comparacao_ia WHERE assinatura = %s", (assinatura(ids),),
        "comparação gravada",
    )


def listar(limite=30):
    return catalogo.consultar(
        f"""SELECT id, objetos, rotulos, provedor, modelo, gerado_em, gerado_por
              FROM catalogo.comparacao_ia ORDER BY gerado_em DESC LIMIT {int(limite)}""",
        (), "comparações gravadas",
    )


def vencida(gravada, objetos):
    """Algum objeto foi reimportado depois da analise."""
    return bool(gravada) and any(o["atualizado_em"] > gravada["gerado_em"] for o in objetos)
