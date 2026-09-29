"""Leitura tolerante do CSV que o time exporta do Excel.

O mesmo arquivo chega de jeitos diferentes conforme quem exporta: `;` ou `,`,
decimal com vírgula ou ponto, "R$ 1.234,56", data dd/mm/aaaa ou o número serial
do Excel, BOM no começo, linhas de total antes do cabeçalho. Aqui tudo isso vira
tipos Python; o que não dá para converter volta como erro da linha, sem
derrubar a carga.
"""

import csv
import datetime
import decimal
import io
import re
import unicodedata

EPOCA_EXCEL = datetime.date(1899, 12, 30)
ERROS_EXCEL = {"#N/D", "#N/A", "#VALUE!", "#VALOR!", "#REF!", "#DIV/0!", "#NOME?", "#NAME?", "#NUM!"}
VAZIOS = {"", "-", "--", "N/A"}


class CsvInvalido(Exception):
    """O arquivo não serve: vazio, sem cabeçalho reconhecível, coluna obrigatória faltando."""


def normalizar(nome):
    """'DATA ENTREGA  FATURAMENTO ' -> 'DATA ENTREGA FATURAMENTO'. Sem acento, caixa alta, espaço único."""
    sem_acento = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.upper().replace("﻿", "").split())


def decodificar(conteudo):
    """bytes -> str. UTF-8 (com ou sem BOM) primeiro; o Excel em pt-BR costuma salvar em cp1252."""
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin-1")


def _separador(texto):
    amostra = "\n".join(texto.splitlines()[:20])
    return ";" if amostra.count(";") >= amostra.count(",") else ","


def ler_linhas(conteudo, marcadores=("EMPRESA", "PROTOCOLO")):
    """Devolve (cabecalho, linhas, numero_da_linha_do_cabecalho).

    O cabeçalho é a primeira linha que contém todos os `marcadores` -- assim as
    linhas de total e parâmetro que a planilha tem em cima (1 a 5) são puladas
    sozinhas, qualquer que seja o recorte que o time exportou.
    """
    texto = decodificar(conteudo) if isinstance(conteudo, bytes) else conteudo
    if not texto.strip():
        raise CsvInvalido("arquivo vazio")
    leitor = csv.reader(io.StringIO(texto), delimiter=_separador(texto))
    brutas = list(leitor)
    for indice, linha in enumerate(brutas[:50]):
        nomes = {normalizar(c) for c in linha}
        if all(m in nomes for m in marcadores):
            cabecalho = [normalizar(c) for c in linha]
            corpo = [l for l in brutas[indice + 1:] if any(c.strip() for c in l)]
            return cabecalho, corpo, indice + 1
    raise CsvInvalido(
        f"cabeçalho não encontrado: nenhuma das 50 primeiras linhas tem as colunas {', '.join(marcadores)}"
    )


# --------------------------------------------------------------------------
# Conversões
# --------------------------------------------------------------------------


def texto(valor):
    valor = (valor or "").strip()
    if valor.upper() in ERROS_EXCEL:
        return None
    return valor or None


def numero(valor):
    """'R$ 1.234,56' / '1234.56' / '(10,00)' / '-' -> Decimal ou None. Levanta ValueError se for lixo."""
    bruto = (valor or "").strip()
    if bruto.upper() in VAZIOS or bruto.upper() in ERROS_EXCEL:
        return None
    negativo = bruto.startswith("(") and bruto.endswith(")")
    limpo = re.sub(r"[R$\s()]", "", bruto)
    if not limpo:
        return None
    if "," in limpo:
        # pt-BR: ponto é milhar, vírgula é decimal
        limpo = limpo.replace(".", "").replace(",", ".")
    elif limpo.count(".") > 1:
        limpo = limpo.replace(".", "")
    # Decimal() aceita "_" entre dígitos e "NaN"/"Infinity": só passa número mesmo.
    if not re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", limpo):
        raise ValueError(f"'{bruto}' não é número")
    try:
        numero_ = decimal.Decimal(limpo)
    except decimal.InvalidOperation as falha:
        raise ValueError(f"'{bruto}' não é número") from falha
    return -numero_ if negativo else numero_


def data(valor):
    """'18/11/2025', '2025-11-18', '18/11/25' ou serial do Excel '45979' -> date."""
    bruto = (valor or "").strip()
    if bruto.upper() in VAZIOS or bruto.upper() in ERROS_EXCEL or bruto == "0":
        return None
    bruto = bruto.split(" ")[0]
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(bruto, formato).date()
        except ValueError:
            continue
    if not re.fullmatch(r"\d+([.,]\d+)?", bruto):
        raise ValueError(f"'{bruto}' não é data")
    serial = float(bruto.replace(",", "."))
    if 1 <= serial < 80000:
        return EPOCA_EXCEL + datetime.timedelta(days=int(serial))
    raise ValueError(f"'{bruto}' não é data")


def inteiro(valor):
    n = numero(valor)
    return None if n is None else int(n)


def booleano(valor):
    bruto = (valor or "").strip().upper()
    if not bruto:
        return None
    if bruto in {"1", "S", "SIM", "T", "TRUE", "V", "VERDADEIRO"}:
        return True
    if bruto in {"0", "N", "NAO", "NÃO", "F", "FALSE", "FALSO"}:
        return False
    raise ValueError(f"'{valor}' não é sim/não")


CONVERSORES = {"texto": texto, "numero": numero, "data": data, "inteiro": inteiro, "booleano": booleano}
