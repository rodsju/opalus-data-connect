"""Formulário de evolução (linha de uma tabela TD*) -> campos legíveis, e o que mudou entre evoluções.

A evolução do ERP IW é um formulário: cada template grava numa tabela TD* larga
(TDWD_VISITAS_HSP tem ~1.000 colunas) e GLBTEMPLATEVAR dá rótulo e domínio de
cada campo. Só entram campos com rótulo -- o resto é controle interno.

O profissional copia a evolução anterior e edita: em out/2026, 97% das evoluções
médicas consecutivas tinham o mesmo "quadro clínico". Por isso a leitura útil é
a primeira do período inteira e, depois, só o que mudou (`com_mudancas`).

Tudo aqui é puro (sem banco), para testar.
"""

import datetime
import html
import re

LIMITE_VALOR = 600

# Campo que identifica pessoa (profissional, cuidador, contato) não sai daqui.
_IDENTIFICA = re.compile(r"RESPONS|REPONS|COREN|\bCRM|CPF|\bRG\b|TELEF|FONE|CELULAR|ENDERE|E_?MAIL|ASSINA|NOME",
                         re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_ESPACO = re.compile(r"\s+")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_TELEFONE = re.compile(r"(\(?\b\d{2}\)?\s?)?\b9?\d{4}-?\d{4}\b")


def dominio(texto):
    """'value|0|.|10|Eupneico|20|Taquipneico' -> {'0': '.', '10': 'Eupneico', ...}. Vazio se não houver."""
    partes = (texto or "").split("|")[1:]
    return {partes[i].strip(): partes[i + 1].strip() for i in range(0, len(partes) - 1, 2)}


def limpar(texto):
    """HTML/RTF de formulário -> texto corrido, cortado."""
    texto = html.unescape(_TAG.sub(" ", str(texto)))
    texto = _ESPACO.sub(" ", texto).strip()
    return texto if len(texto) <= LIMITE_VALOR else texto[:LIMITE_VALOR].rstrip() + "…"


def _numero(valor):
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor)


def valor_legivel(valor, rotulo):
    """Valor cru da coluna + rótulo de GLBTEMPLATEVAR -> texto, ou None quando não diz nada."""
    if valor is None:
        return None
    if isinstance(valor, (datetime.datetime, datetime.date)):
        return f"{valor:%d/%m/%Y}"
    if isinstance(valor, str):
        texto = limpar(valor)
        return texto if texto and texto not in (".", "0") else None
    if hasattr(valor, "quantize"):  # Decimal
        valor = float(valor)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = _numero(valor)
    opcoes = dominio(rotulo.get("dominio"))
    if opcoes:
        texto = opcoes.get(numero)
        # Caixa desmarcada ('positional|0|não|1|sim') não diz nada; 'Não' de pergunta ('value|...') diz.
        marcavel = rotulo.get("checkbox") == 1 or (rotulo.get("dominio") or "").startswith("positional")
        if marcavel and (texto or "").strip().lower() in ("não", "nao"):
            return None
        return texto if texto and texto != "." else None
    if rotulo.get("checkbox") == 1:
        return "sim" if numero == "1" else None
    return None if numero == "0" else numero


def campos(linha, rotulos):
    """Uma linha TD* -> {rótulo: valor} só dos campos rotulados e preenchidos. rotulos: {CAMPO: rótulo}."""
    saida = {}
    for coluna, valor in linha.items():
        rotulo = rotulos.get(coluna.upper())
        if not rotulo or not rotulo.get("rotulo") or _IDENTIFICA.search(coluna) or _IDENTIFICA.search(rotulo["rotulo"]):
            continue
        texto = valor_legivel(valor, rotulo)
        if texto is None:
            continue
        nome = rotulo["rotulo"].strip().rstrip(":")
        # Rótulo repetido no mesmo formulário (ex.: 'Classificação'): desambigua pelo campo
        saida[nome if nome not in saida else f"{nome} ({coluna.lower()})"] = texto
    return saida


def com_mudancas(evolucoes):
    """evolucoes em ordem, cada uma com 'formulario_chave' e 'campos'.

    Acrescenta 'mudou' ({rótulo: valor}; campo apagado vira '(apagado)') e 'base' (True na
    primeira daquele formulário no período, que vai inteira). Devolve a mesma lista.
    """
    anterior = {}
    for e in evolucoes:
        chave = e.get("formulario_chave")
        atual = e.get("campos") or {}
        if chave not in anterior:
            e["base"], e["mudou"] = True, dict(atual)
        else:
            antes = anterior[chave]
            mudou = {k: v for k, v in atual.items() if antes.get(k) != v}
            mudou.update({k: "(apagado)" for k in antes if k not in atual})
            e["base"], e["mudou"] = False, mudou
        if atual:
            anterior[chave] = atual
    return evolucoes


def _partes_nome(nome):
    if not nome:
        return []
    partes = [p for p in re.split(r"\s+", (nome or "").strip()) if len(p) >= 3 and p.lower() not in
              ("das", "dos", "de", "da", "do", "e")]
    return sorted({nome.strip(), *partes} - {""}, key=len, reverse=True)


def higienizar(texto, nome_paciente=None):
    """Tira nome do paciente, CPF e telefone do texto livre antes de mandar para a IA."""
    if not texto:
        return texto
    for parte in _partes_nome(nome_paciente):
        texto = re.sub(rf"\b{re.escape(parte)}\b", "[PACIENTE]", texto, flags=re.IGNORECASE)
    texto = _CPF.sub("[DOC]", texto)
    return _TELEFONE.sub("[TEL]", texto)
