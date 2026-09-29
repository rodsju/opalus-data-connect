"""Peças comuns aos blocos de Glosa Planilha (bloco_gp_*)."""

import datetime

from . import comum

# Status da glosa na ordem do ciclo, com o tom de cada um
STATUS = [
    ("ANÁLISE OPALUS", "amber", "Glosa recebida, ainda sem recurso"),
    ("ANÁLISE OPERADORA", "blue", "Recurso enviado, aguardando a operadora"),
    ("ACATADO / ANÁLISE OPERADORA", "violet", "Parte acatada, parte em recurso"),
    ("ACATADO", "coral", "Opalus aceitou a glosa (perda)"),
    ("PAGO", "teal", "Recurso pago pela operadora"),
    ("GLOSA MANTIDA", "magenta", "Operadora manteve a glosa após o recurso (perda)"),
]
TOM_STATUS = {s: t for s, t, _ in STATUS}

SOMAS = ["linhas", "faturado", "faturado_planilha", "conciliadas", "glosa", "recursado", "acatada", "recuperado_bruto", "recuperado", "mantida"]


def taxas(linha):
    """Acrescenta taxa de glosa e de recuperação (bruto recebido ÷ recursado)."""
    linha["taxa_glosa"] = comum.pct(linha.get("glosa"), linha.get("faturado"))
    linha["taxa_recuperacao"] = comum.pct(linha.get("recuperado_bruto"), linha.get("recursado"))
    return linha


def normalizar(linhas):
    return [taxas({k: (comum.num(v) if k in SOMAS else v) for k, v in l.items()}) for l in linhas]


def amostra_somas(n, faturado, glosa, recursado, acatada, bruto, mantida):
    return {"linhas": n, "faturado": faturado, "glosa": glosa, "recursado": recursado, "acatada": acatada,
            "recuperado_bruto": bruto, "recuperado": bruto * 0.94, "mantida": mantida}


ITEM_FONTE = {
    "chave": "fonte",
    "titulo": "Fonte",
    "negocio": "Planilha base_glosa.xlsx, carregada em Conciliação › Cargas. Desde jul/2025 é ela, não o ERP, "
    "que registra a glosa.",
    "tecnico": "conciliacao.glosa_linha da carga ativa; campos calculados por src/conciliacao/regras.py.",
}


def competencia_rotulo(data):
    if isinstance(data, datetime.date):
        return comum.rotulo_mes(data)
    return "sem competência" if data is None else str(data)
