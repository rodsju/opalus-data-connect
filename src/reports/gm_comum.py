"""Peças comuns aos blocos do relatório Motivos de glosa (bloco_gm_*)."""

from . import comum, gp_comum


def rotulo(motivo, descricao, tamanho=38):
    """'1705 · Valor apresentado a maior' encurtado para eixo de gráfico."""
    texto = (descricao or "").capitalize()
    if len(texto) > tamanho:
        texto = texto[: tamanho - 1] + "…"
    return f"{motivo} · {texto}" if texto else str(motivo)


def desfecho(l):
    """Acrescenta perda, em aberto e as taxas de desfecho numa linha de gp_por_motivo."""
    l["perda"] = l["acatada"] + l["mantida"]
    l["em_aberto"] = max(l["glosa"] - l["recuperado_bruto"] - l["perda"], 0)
    l["pct_recursado"] = comum.pct(l["recursado"], l["glosa"])
    l["pct_recuperado"] = comum.pct(l["recuperado_bruto"], l["glosa"])
    l["pct_perda"] = comum.pct(l["perda"], l["glosa"])
    l["pct_aberto"] = comum.pct(l["em_aberto"], l["glosa"])
    return l


def motivos(linhas):
    return [desfecho(l) for l in comum.ordenar(gp_comum.normalizar(linhas), "glosa")]


def amostra_motivos():
    base = [("1705", "VALOR APRESENTADO A MAIOR", True, "CADASTRO", 2394, 1_830_000, 0.68, 0.27, 0.31),
            ("2401", "TAXA / ALUGUEL INVÁLIDO", False, "OPERADORA", 252, 884_000, 0.85, 0.40, 0.10),
            ("2514", "SERVIÇO NÃO CONTRATADO PARA O PRESTADOR", False, "COMERCIAL", 191, 862_000, 0.90, 0.22, 0.05),
            ("1702", "COBRANÇA DE PROCEDIMENTO EM DUPLICIDADE", False, "FATURAMENTO", 81, 798_000, 0.40, 0.05, 0.50),
            ("3108", "ITEM INCLUSO NO PACOTE NEGOCIADO", True, "COMERCIAL", 60, 310_000, 0.70, 0.35, 0.08)]
    return [{"motivo": m, "descricao": d, "vigente": v, "classificacao": c,
             **gp_comum.amostra_somas(n, g * 5, g, g * r, g * p * 0.8, g * rec, g * p * 0.2)}
            for m, d, v, c, n, g, r, rec, p in base]
