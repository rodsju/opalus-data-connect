"""As colunas da aba BASE OPALUS e como cada uma vira campo no banco.

`calculada=True` marca as colunas que a planilha calcula por fórmula. O app não
confia nelas: recalcula tudo em regras.py e guarda o valor da planilha só para
comparar (campo `<nome>_planilha`). Assim o CSV pode vir com ou sem elas.
"""

from . import csv_leitor

# (campo, tipo, obrigatória, calculada, nomes aceitos no cabeçalho -- já normalizados)
COLUNAS = [
    ("empresa", "texto", True, False, ["EMPRESA"]),
    ("filial", "texto", True, False, ["FILIAL"]),
    ("convenio_formula", "texto", False, True, ["CONVENIO FORMULA"]),
    ("convenio", "texto", True, False, ["CONVENIO", "CONVENIOS"]),
    ("paciente", "texto", True, False, ["PACIENTES ATIVOS POR PERIODO", "PACIENTE", "PACIENTES"]),
    ("mod", "texto", False, False, ["MOD", "MODALIDADE"]),
    ("periodo", "texto", True, False, ["PERIODO ATENDIMENTO", "PERIODO"]),
    ("competencia", "data", False, True, ["COMPETENCIA"]),
    ("protocolo", "texto", False, False, ["PROTOCOLO"]),
    ("valor_faturado", "numero", True, False, ["VALOR FATURADO"]),
    ("data_entrega", "data", False, False, ["DATA ENTREGA FATURAMENTO", "DATA ENTREGA"]),
    ("prazo", "inteiro", False, True, ["PRAZO"]),
    ("data_prevista_recebimento", "data", False, False, ["DATA PREVISTA RECEBIMENTO"]),
    ("data_contratual", "data", False, True, ["DATA PREVISTA CONTRATUAL"]),
    ("mes_previsao", "data", False, True, ["MES (DA PREVISAO)", "MES DA PREVISAO"]),
    ("nota_fiscal", "texto", False, False, ["NOTA FISCAL"]),
    ("valor_liquido", "numero", False, True, ["VALOR LIQUIDO PREVISTO"]),
    ("base_calculo_1", "numero", False, True, ["BASE CALCULO 1"]),
    ("base_calculo_2", "numero", False, True, ["BASE CALCULO 2"]),
    ("glosa", "numero", True, False, ["GLOSA"]),
    ("valor_recebido", "numero", False, False, ["VALOR RECEBIDO C/C", "VALOR RECEBIDO"]),
    ("data_recebimento", "data", False, False, ["DATA RECEBIMENTO"]),
    ("status", "texto", False, True, ["STATUS"]),
    ("dias_atraso", "inteiro", False, True, ["DIAS DE ATRASO"]),
    ("aging", "texto", False, True, ["AGING"]),
    ("obs_financeiro", "texto", False, False, ["OBSERVACOES (FINANCEIRO)"]),
    ("devolucao", "data", False, False, ["DEVOLUCAO"]),
    ("data_reapresentacao", "data", False, False, ["DATA REAPRESENTACAO"]),
    ("protocolo_reapresentacao", "texto", False, False, ["PROTOCOLO REAPRESENTACAO"]),
    ("motivo", "texto", False, False, ["MOTIVO"]),
    ("classificacao_bruta", "texto", False, False, ["CLASSIFICACAO"]),
    ("status_glosa", "texto", False, True, ["STATUS DA GLOSA"]),
    ("prazo_recurso", "data", False, True, ["DATA DE PRAZO P/ RECURSO"]),
    ("valor_recursado", "numero", False, False, ["VALOR RECURSADO"]),
    ("data_recurso", "data", False, False, ["DATA DO RECURSO"]),
    ("protocolo_recurso", "texto", False, False, ["PROTOCOLO DE RECURSO"]),
    ("previsao_pagto_recurso", "data", False, False, ["PREVISAO PAGTO RECURSO"]),
    ("glosa_acatada", "numero", False, False, ["GLOSA ACATADA"]),
    ("data_receb_recurso", "data", False, False, ["DATA RECEBIMENTO RECURSO"]),
    ("valor_recurso_bruto", "numero", False, False, ["VALOR RECURSO RECEBIDO (BRUTO)"]),
    ("valor_recurso_liquido", "numero", False, False, ["VALOR RECURSO RECEBIDO (LIQUIDO)"]),
    ("glosa_mantida", "numero", False, False, ["GLOSA MANTIDA"]),
    ("nf_recurso", "texto", False, False, ["NOTA FISCAL RECURSO"]),
    ("observacao", "texto", False, False, ["OBSERVACAO"]),
    ("banco", "texto", False, False, ["BANCO DO RECEBIDO", "BANCO"]),
]

CAMPOS = [c[0] for c in COLUNAS]
CALCULADAS = [c[0] for c in COLUNAS if c[3]]
DIGITADAS = [c[0] for c in COLUNAS if not c[3]]


def mapear(cabecalho):
    """cabecalho normalizado -> ({campo: índice}, faltando_obrigatórias, desconhecidas)."""
    indice = {}
    for campo, _, _, _, nomes in COLUNAS:
        for nome in nomes:
            if nome in cabecalho:
                indice[campo] = cabecalho.index(nome)
                break
    conhecidas = {n for c in COLUNAS for n in c[4]}
    faltando = [c[4][0] for c in COLUNAS if c[2] and c[0] not in indice]
    desconhecidas = [n for n in cabecalho if n and n not in conhecidas]
    return indice, faltando, desconhecidas


def converter(linha, indice):
    """Uma linha do CSV -> (registro, erros). Campo calculado vira `<campo>_planilha`."""
    registro, erros = {}, []
    tipos = {c[0]: (c[1], c[3]) for c in COLUNAS}
    for campo, posicao in indice.items():
        tipo, calculada = tipos[campo]
        bruto = linha[posicao] if posicao < len(linha) else ""
        destino = f"{campo}_planilha" if calculada else campo
        try:
            registro[destino] = csv_leitor.CONVERSORES[tipo](bruto)
        except ValueError as falha:
            registro[destino] = None
            # Coluna calculada com lixo não reprova a linha: o app recalcula.
            if not calculada:
                erros.append(f"{campo}: {falha}")
    for campo, _, obrigatoria, calculada, _ in COLUNAS:
        if obrigatoria and not calculada and registro.get(campo) in (None, ""):
            erros.append(f"{campo}: obrigatório e veio vazio")
    return registro, erros
