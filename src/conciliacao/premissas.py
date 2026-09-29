"""Tabelas de apoio da planilha (imposto, prazos, de-para, aging) no Postgres.

Cada tipo corresponde a uma tabela nomeada do base_glosa.xlsx. A carga é
sempre por substituição: o CSV enviado vira o conteúdo inteiro da tabela,
porque é assim que o time mantém isso na planilha. Chave repetida fica com a
PRIMEIRA ocorrência, que é a que o XLOOKUP do Excel encontraria.
"""

import logging
import pathlib

from .. import catalogo
from . import csv_leitor, regras

logger = logging.getLogger(__name__)

SEMENTES = pathlib.Path(__file__).resolve().parents[2] / "data" / "conciliacao"

# tipo -> definição. colunas: (nome, conversor); chave: colunas que identificam a linha
TIPOS = {
    "imposto": {
        "tabela": "premissa_imposto",
        "titulo": "Imposto retido por convênio",
        "origem": "PREMISSAS",
        "descricao": "Alíquota retida pela operadora, por empresa + convênio fórmula. Dá o valor líquido.",
        "colunas": [("empresa", "texto"), ("convenio", "texto"), ("imposto", "numero"),
                    ("data_alt1", "data"), ("imposto_alt1", "numero"),
                    ("data_alt2", "data"), ("imposto_alt2", "numero")],
        "chave": ["empresa", "convenio"],
    },
    "prazo": {
        "tabela": "premissa_prazo",
        "titulo": "Prazo de recebimento",
        "origem": "PRAZO_RECEBIMENTO",
        "descricao": "Dias entre a entrega do faturamento e o pagamento previsto, por convênio fórmula.",
        "colunas": [("convenio", "texto"), ("prazo", "inteiro")],
        "chave": ["convenio"],
    },
    "recurso": {
        "tabela": "premissa_recurso",
        "titulo": "Prazo de recurso",
        "origem": "PREMISSAS_RECURSO",
        "descricao": "Dias para recorrer da glosa após o recebimento, e como recorrer, por convênio.",
        "colunas": [("convenio", "texto"), ("prazo_recurso", "inteiro"), ("previsao_pagto", "inteiro"),
                    ("como_recursar", "texto"), ("obs", "texto")],
        "chave": ["convenio"],
    },
    "de_para": {
        "tabela": "convenio_de_para",
        "titulo": "De-para de convênio",
        "origem": "TABELA_CONVENIO_FORMULA",
        "descricao": "Nome do convênio digitado → convênio fórmula, que é a chave de imposto e prazo.",
        "colunas": [("empresa", "texto"), ("convenio", "texto"), ("convenio_formula", "texto")],
        "chave": ["empresa", "convenio"],
    },
    "aging": {
        "tabela": "aging_faixa",
        "titulo": "Faixas de aging",
        "origem": "Guia_Aging",
        "descricao": "Primeiro dia de cada faixa de atraso.",
        "colunas": [("dia", "inteiro"), ("grupo", "texto")],
        "chave": ["dia"],
    },
    "empresa_convenio": {
        "tabela": "empresa_convenio",
        "titulo": "Empresa × filial × convênio",
        "origem": "Tabela11",
        "descricao": "Categoria da nota (PRE/POS) e CNPJ emissor por empresa, filial e convênio.",
        "colunas": [("empresa", "texto"), ("filial", "texto"), ("convenio", "texto"),
                    ("categoria_nf", "texto"), ("cnpj", "texto")],
        "chave": ["empresa", "filial", "convenio"],
    },
    "leitos": {
        "tabela": "parametro_leitos",
        "titulo": "Leitos por unidade",
        "origem": "parâmetro (não existe no ERP)",
        "descricao": "Capacidade de leitos de cada unidade de hospital de transição (nome do provider, ex.: "
        "'Premier Barra HSP'), com data de vigência. Base da taxa de ocupação; tipo_atendimento 0 = hospital "
        "de transição.",
        "colunas": [("unidade", "texto"), ("tipo_atendimento", "inteiro"), ("leitos", "inteiro"),
                    ("vigente_desde", "data")],
        "chave": ["unidade", "vigente_desde"],
    },
    "motivo_preauditoria": {
        "tabela": "motivo_preauditoria",
        "titulo": "Motivos internos da pré-auditoria",
        "origem": "parâmetro (o ERP só guarda o código)",
        "descricao": "Descrição dos códigos internos (1 a 4) de CAPPAYMENTITEM.PREAUDITBILLREASON. Os demais "
        "códigos são TISS e vêm da Tabela 38. Semente inferida dos comentários dos auditores: confirme.",
        "colunas": [("codigo", "texto"), ("descricao", "texto")],
        "chave": ["codigo"],
    },
    "motivo_tiss": {
        "tabela": "motivo_tiss",
        "titulo": "Motivos de glosa (TISS)",
        "origem": "Tabela 38 do Padrão TISS (ANS)",
        "descricao": "Descrição dos códigos da coluna MOTIVO. Sincronizada com a ANS pelo botão abaixo; o CSV "
        "substitui a tabela inteira.",
        "colunas": [("codigo", "texto"), ("descricao", "texto"), ("vigente", "booleano"), ("versao", "texto")],
        "chave": ["codigo"],
    },
}

# arquivo de semente de cada tipo (gerado por scripts/extrair_premissas_xlsx.py)
ARQUIVO_SEMENTE = {
    "imposto": "premissa_imposto.csv", "prazo": "premissa_prazo.csv", "recurso": "premissa_recurso.csv",
    "de_para": "convenio_de_para.csv", "aging": "aging_faixa.csv", "empresa_convenio": "empresa_convenio.csv",
    "leitos": "parametro_leitos.csv", "motivo_preauditoria": "motivo_preauditoria.csv",
}


# Motivos TISS vêm da ANS (sincronização) e não se editam à mão
EDITAVEIS = [t for t in TIPOS if t != "motivo_tiss"]
# Guardadas como fração (0,0615); na tela e no formulário, em % (6,15)
PERCENTUAIS = {"imposto", "imposto_alt1", "imposto_alt2"}


class PremissaInvalida(Exception):
    def __init__(self, motivo, detalhe=""):
        super().__init__(motivo)
        self.motivo = motivo
        self.detalhe = detalhe


def ler_csv(tipo, conteudo):
    """CSV -> (linhas, avisos). Cabeçalho pelos nomes das colunas do tipo, em qualquer ordem."""
    definicao = TIPOS[tipo]
    nomes = [c for c, _ in definicao["colunas"]]
    obrigatorias = definicao["chave"]
    try:
        cabecalho, corpo, _ = csv_leitor.ler_linhas(conteudo, [csv_leitor.normalizar(c) for c in obrigatorias])
    except csv_leitor.CsvInvalido as falha:
        raise PremissaInvalida(str(falha), f"colunas esperadas: {', '.join(nomes)}") from falha

    posicao = {c: cabecalho.index(csv_leitor.normalizar(c)) for c in nomes
               if csv_leitor.normalizar(c) in cabecalho}
    linhas, avisos, vistas = [], [], set()
    for numero, bruta in enumerate(corpo, start=2):
        registro = {}
        for coluna, tipo_col in definicao["colunas"]:
            valor = bruta[posicao[coluna]] if coluna in posicao and posicao[coluna] < len(bruta) else ""
            try:
                registro[coluna] = csv_leitor.CONVERSORES[tipo_col](valor)
            except ValueError as falha:
                # Ex.: prazo de recurso "PRÉ" -- a linha fica, sem o valor.
                registro[coluna] = None
                avisos.append(f"linha {numero}, {coluna}: {falha} (gravado vazio)")
        if any(registro[c] in (None, "") for c in obrigatorias):
            continue
        identidade = tuple(regras.chave(str(registro[c])) for c in obrigatorias)
        if identidade in vistas:
            avisos.append(f"linha {numero}: {' / '.join(str(registro[c]) for c in obrigatorias)} repetido "
                          "(vale a primeira ocorrência, como no XLOOKUP)")
            continue
        vistas.add(identidade)
        linhas.append(registro)
    if not linhas:
        raise PremissaInvalida("nenhuma linha válida no arquivo", f"colunas esperadas: {', '.join(nomes)}")
    return linhas, avisos


def ler_semente(tipo):
    return ler_csv(tipo, (SEMENTES / ARQUIVO_SEMENTE[tipo]).read_bytes())


# --------------------------------------------------------------------------
# Postgres
# --------------------------------------------------------------------------


def gravar(tipo, linhas, conexao=None):
    """Substitui a tabela inteira numa transação só."""
    import psycopg

    definicao = TIPOS[tipo]
    colunas = [c for c, _ in definicao["colunas"]]
    tabela = f'conciliacao.{definicao["tabela"]}'
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({', '.join(['%s'] * len(colunas))})"
    try:
        with psycopg.connect(catalogo.DSN, connect_timeout=5) as con:
            with con.cursor() as cur:
                cur.execute(f"DELETE FROM {tabela}")
                cur.executemany(sql, [[l.get(c) for c in colunas] for l in linhas])
    except Exception as falha:
        raise catalogo.ConsultaFalhou(f"gravar premissa {tipo}", falha) from falha


def listar(tipo):
    definicao = TIPOS[tipo]
    colunas = ", ".join(c for c, _ in definicao["colunas"])
    if tipo in EDITAVEIS:
        colunas = "id, " + colunas
    ordem = ", ".join(definicao["chave"])
    return catalogo.consultar(
        f'SELECT {colunas} FROM conciliacao.{definicao["tabela"]} ORDER BY {ordem}', (), f"premissa {tipo}"
    )


def contagens():
    """{tipo: linhas} para a página de premissas."""
    partes = " UNION ALL ".join(
        f"SELECT '{t}' AS tipo, COUNT(*) AS n FROM conciliacao.{d['tabela']}" for t, d in TIPOS.items()
    )
    return {l["tipo"]: l["n"] for l in catalogo.consultar(partes, (), "contagem das premissas")}


def carregar():
    """Premissas do banco no formato que regras.calcular usa."""
    return regras.Premissas.de_linhas(
        de_para=listar("de_para"), imposto=listar("imposto"), prazo=listar("prazo"),
        recurso=listar("recurso"), aging=listar("aging"),
    )


def carregar_sementes():
    """Premissas direto dos CSVs de semente, sem banco (testes e validação)."""
    return regras.Premissas.de_linhas(**{
        chave_: ler_semente(tipo)[0]
        for chave_, tipo in (("de_para", "de_para"), ("imposto", "imposto"), ("prazo", "prazo"),
                             ("recurso", "recurso"), ("aging", "aging"))
    })


def semear():
    """Grava todas as sementes de data/conciliacao. Devolve {tipo: (linhas, avisos)}."""
    resultado = {}
    for tipo in ARQUIVO_SEMENTE:
        linhas, avisos = ler_semente(tipo)
        gravar(tipo, linhas)
        resultado[tipo] = (len(linhas), avisos)
    return resultado


# --------------------------------------------------------------------------
# Edição linha a linha (tudo menos motivo_tiss)
# --------------------------------------------------------------------------


def ler_formulario(tipo, campos):
    """Campos do formulário (texto) -> registro convertido. PremissaInvalida com o campo que falhou."""
    if tipo not in EDITAVEIS:
        raise PremissaInvalida(f"'{tipo}' não é editável")
    registro = {}
    for coluna, tipo_col in TIPOS[tipo]["colunas"]:
        bruto = (campos.get(coluna) or "").strip()
        try:
            valor = csv_leitor.CONVERSORES[tipo_col](bruto)
        except ValueError as falha:
            raise PremissaInvalida(f"{coluna}: {falha}") from falha
        if coluna in PERCENTUAIS and valor is not None:
            valor = valor / 100
        registro[coluna] = valor
    faltando = [c for c in TIPOS[tipo]["chave"] if registro[c] in (None, "")]
    if faltando:
        raise PremissaInvalida("campo obrigatório vazio", ", ".join(faltando))
    return registro


def _identidade(tipo, registro):
    return tuple(regras.chave(str(registro[c])) for c in TIPOS[tipo]["chave"])


def _checar_repetida(tipo, registro, ignorar_id=None):
    """A chave do tipo (ex.: empresa + convênio) não pode repetir: o XLOOKUP pegaria só uma."""
    alvo = _identidade(tipo, registro)
    for l in listar(tipo):
        if l["id"] != ignorar_id and _identidade(tipo, l) == alvo:
            raise PremissaInvalida("já existe uma linha com essa chave",
                                   " / ".join(f"{c} = {registro[c]}" for c in TIPOS[tipo]["chave"]))


def _executar(sql, params, descricao):
    import psycopg

    try:
        with psycopg.connect(catalogo.DSN, connect_timeout=5) as con:
            with con.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount
    except Exception as falha:
        raise catalogo.ConsultaFalhou(descricao, falha) from falha


def criar(tipo, registro, autor=None):
    _checar_repetida(tipo, registro)
    colunas = [c for c, _ in TIPOS[tipo]["colunas"]]
    _executar(f'INSERT INTO conciliacao.{TIPOS[tipo]["tabela"]} ({", ".join(colunas)}) '
              f'VALUES ({", ".join(["%s"] * len(colunas))})', [registro[c] for c in colunas], f"incluir premissa {tipo}")
    logger.info("premissas: %s incluiu linha em %s", autor or "anônimo", tipo)


def atualizar(tipo, id_linha, registro, autor=None):
    _checar_repetida(tipo, registro, ignorar_id=id_linha)
    colunas = [c for c, _ in TIPOS[tipo]["colunas"]]
    n = _executar(f'UPDATE conciliacao.{TIPOS[tipo]["tabela"]} SET {", ".join(f"{c} = %s" for c in colunas)} '
                  "WHERE id = %s", [registro[c] for c in colunas] + [id_linha], f"alterar premissa {tipo}")
    if not n:
        raise PremissaInvalida("linha não encontrada", f"id {id_linha}")
    logger.info("premissas: %s alterou a linha %s de %s", autor or "anônimo", id_linha, tipo)


def excluir(tipo, id_linha, autor=None):
    if tipo not in EDITAVEIS:
        raise PremissaInvalida(f"'{tipo}' não é editável")
    n = _executar(f'DELETE FROM conciliacao.{TIPOS[tipo]["tabela"]} WHERE id = %s', [id_linha],
                  f"excluir premissa {tipo}")
    if not n:
        raise PremissaInvalida("linha não encontrada", f"id {id_linha}")
    logger.info("premissas: %s excluiu a linha %s de %s", autor or "anônimo", id_linha, tipo)
