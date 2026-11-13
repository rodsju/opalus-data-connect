"""SQLs de negócio dos /reports, dialeto BigQuery (GoogleSQL), sobre a camada bronze.

Tradução à mão de sql_oracle.py, com as MESMAS chaves em CONSULTAS: os blocos
pedem pelo nome via fonte.rodar() e não sabem qual banco respondeu. As regras de
negócio (cascata da conta, particular, situação) são as de lá -- os comentários
completos continuam em sql_oracle.py. Número diferente entre os dois é bug.

Dataset: as tabelas são escritas como {ds}.TABELA. fonte_bq troca {ds} por
`BQ_PROJECT.BQ_DATASET` na hora de rodar, então o schema nunca fica fixo aqui.

Binds: @DT_INI, @DT_FIM (exclusivo), @UNIDADE, @TIPO e @ID. Tipados em
fonte_bq.TIPOS_BIND (NULL precisa de tipo no BigQuery).

Diferenças de dialeto que importam:
- Oracle trata '' como NULL; o BigQuery não. Texto "vazio" vira NULLIF(TRIM(x), '').
- INT64 não concatena com texto: CAST(... AS STRING) antes do ||.

Migração em andamento: só as consultas da página Faturamento (e dos filtros)
estão aqui. As demais chaves de sql_oracle.CONSULTAS falham com "ainda não
migrada" até serem portadas.
"""

# Cascata da conta: bruto → pacote → pré-auditoria → cobrado (faturamento_grupo)
# = particular + fatura_operadora. Ver sql_oracle.py.
COBRADO_ITEM = "i.UNITPRICE * (i.QUANTITY - IFNULL(i.COVERAGEQUANTITY, 0))"
COBERTO_ITEM = "i.UNITPRICE * IFNULL(i.COVERAGEQUANTITY, 0)"
# Só quantidades positivas: estorno (BILLTYPE 1) tem cobertura negativa e não é corte.
PRE_AUDITORIA_ITEM = ("CASE WHEN IFNULL(i.PREAUDITBILLQUANT, 0) > 0 AND IFNULL(i.COVERAGEQUANTITY, 0) > 0 "
                      "THEN i.UNITPRICE * LEAST(i.PREAUDITBILLQUANT, i.COVERAGEQUANTITY) ELSE 0 END")
PACOTE_ITEM = f"({COBERTO_ITEM} - {PRE_AUDITORIA_ITEM})"
TRIBUTO_ITEM = "CASE WHEN i.RESOURCETYPE = 15 THEN i.UNITCOST * i.QUANTITY ELSE 0 END"
DESCONTO_ITEM = "IFNULL(i.DISCOUNT, 0) + IFNULL(i.DISCOUNTITEM, 0)"

EH_PARTICULAR = "IFNULL(op.CORPORATION, 0) = 1"

CASCATA_SOMA = f"""ROUND(SUM({COBRADO_ITEM} + {COBERTO_ITEM}), 2)                        AS bruto,
       ROUND(SUM({PACOTE_ITEM}), 2)                                          AS pacote,
       ROUND(SUM({PRE_AUDITORIA_ITEM}), 2)                                   AS pre_auditoria,
       ROUND(SUM({COBRADO_ITEM}), 2)                                         AS faturamento_grupo,
       ROUND(SUM(CASE WHEN {EH_PARTICULAR} THEN {COBRADO_ITEM} ELSE 0 END), 2)     AS particular,
       ROUND(SUM(CASE WHEN {EH_PARTICULAR} THEN 0 ELSE {COBRADO_ITEM} END), 2)     AS fatura_operadora,
       ROUND(SUM({TRIBUTO_ITEM}), 2)                                         AS tributos_erp,
       ROUND(SUM({DESCONTO_ITEM}), 2)                                        AS desconto_informativo"""

FATURA_OPERADORA = f"CASE WHEN {EH_PARTICULAR} THEN 0 ELSE {COBRADO_ITEM} END"
TIPO_PAGADOR = f"CASE WHEN {EH_PARTICULAR} THEN 'particular' ELSE 'operadora' END"

TIPO_ATENDIMENTO = ("CASE ta.ADMISSIONTYPE WHEN 0 THEN 'Hospital de transição' WHEN 1 THEN 'Home care' "
                    "WHEN 3 THEN 'Ambulatorial' ELSE 'Outro' END")

JOIN_TIPO_ITEM = "LEFT JOIN {ds}.CAPADMISSION ta ON ta.ID = i.IDADMISSION"
FILTRO_TIPO = "(@TIPO IS NULL OR ta.ADMISSIONTYPE = @TIPO)"

FILTRO_HOMECARE = "(@UNIDADE IS NULL OR UPPER(TRIM(hc.NAME)) = UPPER(TRIM(@UNIDADE)))"
FILTRO_PROVIDER = "(@UNIDADE IS NULL OR UPPER(TRIM(hp.NAME)) = UPPER(TRIM(@UNIDADE)))"

SITUACAO_CONTA = """CASE
        WHEN {a}.SIMULATION = 1 THEN 'Simulação'
        WHEN {a}.WRITEOFF   = 1 THEN 'Baixada (write-off)'
        WHEN {a}.LIBERATED  = 0 THEN 'Aberta (não liberada)'
        WHEN {a}.EXPORTED   = 0 THEN 'Liberada (não exportada)'
        ELSE 'Exportada (fechada)'
    END"""

VALOR_ORCAMENTO = """(SELECT IFNULL(SUM(bi.UNITPRICE * (bi.QUANTITY - IFNULL(bi.COVERAGEQUANTITY, 0))), 0)
           FROM {ds}.CAPBUDGETITEM bi WHERE bi.IDBUDGET = b.ID)"""

JOIN_UNIDADE_ORCAMENTO = """JOIN {ds}.CAPADMISSION a ON a.ID = b.IDADMISSION
LEFT JOIN {ds}.GLBHEALTHPROVDEP d ON d.ID = a.IDHEALTHPROVDEP
LEFT JOIN {ds}.GLBHEALTHPROVIDER hp ON hp.ID = d.IDHEALTHPROVIDER"""

PERIODO_CONTA = "p.STARTDATE >= @DT_INI AND p.STARTDATE < @DT_FIM"

SQL_PACIENTE_NOME = """
SELECT pe.NAME AS nome
  FROM {ds}.GLBPATIENT pt
  JOIN {ds}.GLBPERSON pe ON pe.ID = pt.IDPERSON
 WHERE pt.ID = @ID
"""

SQL_UNIDADES_FATURAM = """
SELECT e.ID        AS id_homecare,
       e.NAME      AS unidade,
       e.FULLNAME  AS razao_social,
       e.IDNUMBER1 AS cnpj
  FROM {ds}.GLBENTERPRISE e
 WHERE EXISTS (SELECT 1 FROM {ds}.CAPPAYMENT p WHERE p.IDHOMECARE = e.ID)
 ORDER BY e.NAME
"""

SQL_UNIDADES_CANONICAS = """
SELECT hp.ID             AS id_health_provider,
       hp.NAME           AS unidade_negocio,
       hp.HEALTHCARETYPE AS tipo_assistencia,
       hp.INACTIVE       AS inativa,
       e.ID              AS id_homecare,
       e.NAME            AS empresa_homecare
  FROM {ds}.GLBHEALTHPROVIDER hp
  LEFT JOIN {ds}.GLBENTERPRISE e ON e.ID = hp.IDENTERPRISE
 ORDER BY hp.NAME
"""

SQL_CONTAS_POR_STATUS = f"""
WITH contas AS (
    SELECT p.ID, p.IDHOMECARE,
           p.SIMULATION, p.LIBERATED, p.EXPORTED, p.WRITEOFF, p.COLLECTION,
           {CASCATA_SOMA}
      FROM {{ds}}.CAPPAYMENT p
      JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
      {JOIN_TIPO_ITEM}
      LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
     WHERE {PERIODO_CONTA}
       AND {FILTRO_TIPO}
     GROUP BY p.ID, p.IDHOMECARE,
              p.SIMULATION, p.LIBERATED, p.EXPORTED, p.WRITEOFF, p.COLLECTION
), classificadas AS (
    SELECT IFNULL(hc.NAME, '(sem unidade)') AS unidade,
           {SITUACAO_CONTA.format(a='c')} AS situacao,
           c.*
      FROM contas c
      LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = c.IDHOMECARE
     WHERE {FILTRO_HOMECARE}
)
SELECT unidade,
       situacao,
       COUNT(*)                         AS contas,
       ROUND(SUM(bruto), 2)             AS bruto,
       ROUND(SUM(pacote), 2)            AS pacote,
       ROUND(SUM(pre_auditoria), 2)     AS pre_auditoria,
       ROUND(SUM(faturamento_grupo), 2) AS faturamento_grupo,
       ROUND(SUM(particular), 2)        AS particular,
       ROUND(SUM(fatura_operadora), 2)  AS fatura_operadora,
       ROUND(SUM(tributos_erp), 2)      AS tributos_erp
  FROM classificadas
 GROUP BY unidade, situacao
 ORDER BY unidade, faturamento_grupo DESC
"""

SQL_GAP_RESUMO = f"""
SELECT IFNULL(hp.NAME, '(sem unidade)')           AS unidade,
       COUNT(*)                                   AS autorizados_sem_faturamento,
       ROUND(SUM({VALOR_ORCAMENTO}), 2)           AS valor_autorizado_pendente
  FROM {{ds}}.CAPBUDGET b
  {JOIN_UNIDADE_ORCAMENTO}
 WHERE b.AUTHORIZEXTSTATUS = 1
   AND b.CANCELED = 0
   AND b.STARTDATE >= @DT_INI
   AND b.STARTDATE <  @DT_FIM
   AND (@TIPO IS NULL OR a.ADMISSIONTYPE = @TIPO)
   AND {FILTRO_PROVIDER}
   AND NOT EXISTS (SELECT 1 FROM {{ds}}.CAPPAYMENTITEM pi WHERE pi.IDBUDGET = b.ID)
 GROUP BY unidade
 ORDER BY valor_autorizado_pendente DESC
"""

SQL_GLOSA_POR_UNIDADE = f"""
SELECT IFNULL(hc.NAME, '(sem unidade)')                     AS unidade,
       COUNT(*)                                             AS itens,
       COUNTIF(i.AUDITBILLVALUE > 0)                        AS itens_glosados,
       ROUND(SUM({FATURA_OPERADORA}), 2)                    AS fatura_operadora,
       ROUND(SUM(IFNULL(i.AUDITBILLVALUE, 0)), 2)           AS glosa,
       ROUND(SUM(IFNULL(i.AUDITBILLSUSTAINED, 0)), 2)       AS glosa_sustentada,
       ROUND(SUM(IFNULL(i.AUDITBILLRECOVERED, 0)), 2)       AS glosa_recuperada,
       ROUND(SUM(IFNULL(i.AUDITBILLVALUE, 0)) /
             NULLIF(SUM({FATURA_OPERADORA}), 0) * 100, 2)   AS taxa_glosa_pct
  FROM {{ds}}.CAPPAYMENTITEM i
  JOIN {{ds}}.CAPPAYMENT p ON p.ID = i.IDPAYMENT
  {JOIN_TIPO_ITEM}
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND {PERIODO_CONTA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY unidade
 ORDER BY glosa DESC
"""

SQL_FATURAMENTO_POR_OPERADORA = f"""
SELECT IFNULL(hc.NAME, '(sem unidade)')      AS unidade,
       IFNULL(op.NAME, '(sem entidade)')     AS operadora,
       {TIPO_PAGADOR}                        AS pagador,
       COUNT(DISTINCT p.ID)                  AS contas,
       {CASCATA_SOMA}
  FROM {{ds}}.CAPPAYMENT p
  JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  {JOIN_TIPO_ITEM}
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND {PERIODO_CONTA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY unidade, operadora, pagador
 ORDER BY faturamento_grupo DESC
"""

SQL_CONTAS_EM_ABERTO = f"""
SELECT IFNULL(op.NAME, '(sem entidade)')     AS operadora,
       {TIPO_PAGADOR}                        AS pagador,
       COUNT(DISTINCT p.ID)                  AS contas_abertas,
       {CASCATA_SOMA}
  FROM {{ds}}.CAPPAYMENT p
  JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  {JOIN_TIPO_ITEM}
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND p.WRITEOFF = 0
   AND (p.LIBERATED = 0 OR p.EXPORTED = 0)
   AND {PERIODO_CONTA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY operadora, pagador
 ORDER BY faturamento_grupo DESC
"""

# Faturamento › Exportadas sem retorno: uma linha por guia exportada à operadora
# (conta × admissão). Particular fica de fora. Ver sql_oracle.py.
SQL_EXPORTADAS_POR_GUIA = f"""
SELECT p.ID                                  AS id_conta,
       i.IDADMISSION                         AS id_admissao,
       ta.IDPATIENT                          AS id_paciente,
       IFNULL(op.NAME, '(sem entidade)')     AS operadora,
       ROUND(SUM({COBRADO_ITEM}), 2)         AS faturavel
  FROM {{ds}}.CAPPAYMENT p
  JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  {JOIN_TIPO_ITEM}
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE {SITUACAO_CONTA.format(a='p')} = 'Exportada (fechada)'
   AND NOT ({EH_PARTICULAR})
   AND {PERIODO_CONTA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY id_conta, id_admissao, id_paciente, operadora
HAVING SUM({COBRADO_ITEM}) <> 0
"""

DIMENSOES_CASCATA = {
    "mes": "FORMAT_DATETIME('%Y-%m', p.STARTDATE)",
    "unidade": "IFNULL(hc.NAME, '(sem unidade)')",
    "operadora": "IFNULL(op.NAME, '(sem entidade)')",
    "pagador": TIPO_PAGADOR,
    # Nunca o nome: o código interno do paciente no ERP (GLBPATIENT.ID)
    "paciente": "CASE WHEN ta.IDPATIENT IS NULL THEN '(sem paciente)' ELSE 'P' || CAST(ta.IDPATIENT AS STRING) END",
    "tipo_atendimento": TIPO_ATENDIMENTO,
}

SQL_CASCATA = f"""
SELECT {{dimensao}}                            AS grupo,
       COUNT(DISTINCT p.ID)                  AS contas,
       COUNT(DISTINCT i.IDADMISSION)         AS admissoes,
       {CASCATA_SOMA}
  FROM {{ds}}.CAPPAYMENT p
  JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN {{ds}}.CAPADMISSION ta ON ta.ID = i.IDADMISSION
 WHERE p.SIMULATION = 0
   AND {PERIODO_CONTA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY grupo
 ORDER BY faturamento_grupo DESC
"""

# Pré-auditoria: corte ANTES do envio (CAPPAYMENTITEM.PREAUDITBILL*). Ver sql_oracle.py.
DIMENSOES_PRE_AUDITORIA = {
    "motivo": "IFNULL(CAST(i.PREAUDITBILLREASON AS STRING), '(sem motivo)')",
    "operadora": "IFNULL(op.NAME, '(sem entidade)')",
    "unidade": "IFNULL(hc.NAME, '(sem unidade)')",
    "mes": "FORMAT_DATETIME('%Y-%m', p.STARTDATE)",
    "tipo_atendimento": TIPO_ATENDIMENTO,
}
FILTRO_PRE_AUDITORIA = "(IFNULL(i.PREAUDITBILLQUANT, 0) <> 0 OR IFNULL(i.PREAUDITBILLVALUE, 0) <> 0)"

SQL_PRE_AUDITORIA = f"""
SELECT {{dimensao}}                                      AS grupo,
       COUNT(*)                                        AS itens,
       COUNT(DISTINCT p.ID)                            AS contas,
       ROUND(SUM({PRE_AUDITORIA_ITEM}), 2)             AS pre_auditoria,
       ROUND(SUM(IFNULL(i.PREAUDITBILLVALUE, 0)), 2)   AS valor_informado,
       COUNTIF(IFNULL(i.AUDITBILLVALUE, 0) <> 0)       AS itens_glosados_depois,
       ROUND(SUM(IFNULL(i.AUDITBILLVALUE, 0)), 2)      AS glosa_depois
  FROM {{ds}}.CAPPAYMENT p
  JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN {{ds}}.CAPADMISSION ta ON ta.ID = i.IDADMISSION
 WHERE p.SIMULATION = 0
   AND {PERIODO_CONTA}
   AND {FILTRO_PRE_AUDITORIA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY grupo
 ORDER BY pre_auditoria DESC
"""

# Consultas › Pré-auditoria: um item pré-auditado por linha. O comentário do
# auditor pode citar o paciente: a lista só diz se ele existe.
SQL_PRE_AUDITORIA_ITENS = f"""
SELECT i.ID                                         AS id_item,
       p.ID                                         AS id_conta,
       p.STARTDATE                                  AS competencia,
       IFNULL(hc.NAME, '(sem unidade)')             AS unidade,
       IFNULL(op.NAME, '(sem entidade)')            AS operadora,
       ta.ADMISSIONTYPE                             AS tipo,
       i.IDADMISSION                                AS id_admissao,
       ta.IDPATIENT                                 AS id_paciente,
       CASE WHEN ta.IDPATIENT IS NOT NULL THEN 'P' || CAST(ta.IDPATIENT AS STRING) END AS paciente_codigo,
       IFNULL(sc.CODENAME, '(recurso ' || CAST(i.SCRESOURCE AS STRING) || ')') AS recurso,
       i.QUANTITY                                   AS quantidade,
       ROUND(i.UNITPRICE, 4)                        AS preco,
       i.PREAUDITBILLQUANT                          AS qtd_pre,
       ROUND({PRE_AUDITORIA_ITEM}, 2)               AS pre_auditoria,
       ROUND(IFNULL(i.PREAUDITBILLVALUE, 0), 2)     AS valor_informado,
       CAST(i.PREAUDITBILLREASON AS STRING)         AS motivo,
       CASE WHEN NULLIF(TRIM(i.PREAUDITCOMMENTS), '') IS NOT NULL THEN 1 ELSE 0 END AS tem_comentario,
       ROUND(IFNULL(i.AUDITBILLVALUE, 0), 2)        AS glosa_depois
  FROM {{ds}}.CAPPAYMENT p
  JOIN {{ds}}.CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN {{ds}}.GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN {{ds}}.GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN {{ds}}.CAPADMISSION ta ON ta.ID = i.IDADMISSION
  LEFT JOIN {{ds}}.SCCCODE sc ON sc.ID = i.SCRESOURCE
 WHERE p.SIMULATION = 0
   AND {PERIODO_CONTA}
   AND {FILTRO_PRE_AUDITORIA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 ORDER BY p.STARTDATE DESC, pre_auditoria DESC
"""

SQL_PRE_AUDITORIA_COMENTARIO = """
SELECT NULLIF(TRIM(i.PREAUDITCOMMENTS), '') AS comentario
  FROM {ds}.CAPPAYMENTITEM i
 WHERE i.ID = @ID
"""

CONSULTAS = {
    "paciente_nome": SQL_PACIENTE_NOME,
    "unidades_faturam": SQL_UNIDADES_FATURAM,
    "unidades_canonicas": SQL_UNIDADES_CANONICAS,
    "contas_por_status": SQL_CONTAS_POR_STATUS,
    "gap_resumo": SQL_GAP_RESUMO,
    "glosa_por_unidade": SQL_GLOSA_POR_UNIDADE,
    "faturamento_por_operadora": SQL_FATURAMENTO_POR_OPERADORA,
    "contas_em_aberto": SQL_CONTAS_EM_ABERTO,
    "exportadas_por_guia": SQL_EXPORTADAS_POR_GUIA,
    **{f"cascata_por_{nome}": SQL_CASCATA.replace("{dimensao}", DIMENSOES_CASCATA[nome])
       for nome in ("pagador", "mes", "operadora")},
    **{f"pre_auditoria_por_{nome}": SQL_PRE_AUDITORIA.replace("{dimensao}", DIMENSOES_PRE_AUDITORIA[nome])
       for nome in ("motivo", "operadora", "mes")},
    "pre_auditoria_itens": SQL_PRE_AUDITORIA_ITENS,
    "pre_auditoria_comentario": SQL_PRE_AUDITORIA_COMENTARIO,
}
