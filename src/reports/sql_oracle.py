"""SQLs de negócio dos /reports, dialeto Oracle.

Cópia fiel de opalus-mcp-server-01/src/faturamento.py -- as mesmas consultas que
as tools de tools_faturamento.py executam, já conferidas contra o banco. Os
comentários de lá explicam as regras que não se adivinham pelo schema: a
cascata da conta (a operadora recebe preço × (qtd − qtd coberta), não preço ×
qtd), as duas dimensões de unidade e o fim de período exclusivo. Manter em sincronia: número diferente do MCP é bug.

Os blocos não importam estas constantes: pedem pelo nome em CONSULTAS, via
fonte.rodar(). Na migração para o BigQuery nasce um sql_bq.py com as mesmas
chaves, e nenhum bloco muda.

Binds: :DT_INI, :DT_FIM (exclusivo), :UNIDADE e :TIPO (tipo de atendimento; NULL = todos).
"""

# Cascata da conta: bruto → pacote → pré-auditoria → cobrado (faturamento_grupo)
# = particular + fatura_operadora. Validada contra a planilha de glosa (4.875 de
# 5.126 linhas ao centavo); o comentário completo está em faturamento.py do MCP.
# Pré-auditoria: corte ANTES do envio (CAPPAYMENTITEM.PREAUDITBILL*), gravado
# como cobertura -- sai de dentro do coberto, sem mudar bruto nem cobrado.
COBRADO_ITEM = "i.UNITPRICE * (i.QUANTITY - NVL(i.COVERAGEQUANTITY, 0))"
COBERTO_ITEM = "i.UNITPRICE * NVL(i.COVERAGEQUANTITY, 0)"
# Só quantidades positivas: estorno (BILLTYPE 1) tem cobertura negativa e não é corte.
PRE_AUDITORIA_ITEM = ("CASE WHEN NVL(i.PREAUDITBILLQUANT, 0) > 0 AND NVL(i.COVERAGEQUANTITY, 0) > 0 "
                      "THEN i.UNITPRICE * LEAST(i.PREAUDITBILLQUANT, i.COVERAGEQUANTITY) ELSE 0 END")
PACOTE_ITEM = f"({COBERTO_ITEM} - {PRE_AUDITORIA_ITEM})"
TRIBUTO_ITEM = "CASE WHEN i.RESOURCETYPE = 15 THEN i.UNITCOST * i.QUANTITY ELSE 0 END"
DESCONTO_ITEM = "NVL(i.DISCOUNT, 0) + NVL(i.DISCOUNTITEM, 0)"

EH_PARTICULAR = "NVL(op.CORPORATION, 0) = 1"

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

TIPO_PAGADOR = f"CASE WHEN {EH_PARTICULAR} THEN 'particular' ELSE 'operadora' END"

TIPOS_ATENDIMENTO = {0: "Hospital de transição", 1: "Home care", 3: "Ambulatorial"}
TIPO_ATENDIMENTO = ("CASE ta.ADMISSIONTYPE WHEN 0 THEN 'Hospital de transição' WHEN 1 THEN 'Home care' "
                    "WHEN 3 THEN 'Ambulatorial' ELSE 'Outro' END")

TIPO_ATENDIMENTO = ("CASE ta.ADMISSIONTYPE WHEN 0 THEN 'Hospital de transição' WHEN 1 THEN 'Home care' "
                    "WHEN 3 THEN 'Ambulatorial' ELSE 'Outro' END")

JOIN_TIPO_ITEM = "LEFT JOIN CAPADMISSION ta ON ta.ID = i.IDADMISSION"
FILTRO_TIPO = "(:TIPO IS NULL OR ta.ADMISSIONTYPE = :TIPO)"

FILTRO_TIPO = "(:TIPO IS NULL OR ta.ADMISSIONTYPE = :TIPO)"

FILTRO_HOMECARE = (
    "(:UNIDADE IS NULL OR UPPER(TRIM(hc.NAME)) = UPPER(TRIM(:UNIDADE)))"
)
FILTRO_PROVIDER = (
    "(:UNIDADE IS NULL OR UPPER(TRIM(hp.NAME)) = UPPER(TRIM(:UNIDADE)))"
)

FILTRO_PROVIDER = (
    "(:UNIDADE IS NULL OR UPPER(TRIM(hp.NAME)) = UPPER(TRIM(:UNIDADE)))"
)

FILTRO_PROVIDER_OU_HOMECARE = (
    "(:UNIDADE IS NULL"
    " OR UPPER(TRIM(hp.NAME)) = UPPER(TRIM(:UNIDADE))"
    " OR UPPER(TRIM(hc.NAME)) = UPPER(TRIM(:UNIDADE)))"
)

SITUACAO_CONTA = """CASE
        WHEN {a}.SIMULATION = 1 THEN 'Simulação'
        WHEN {a}.WRITEOFF   = 1 THEN 'Baixada (write-off)'
        WHEN {a}.LIBERATED  = 0 THEN 'Aberta (não liberada)'
        WHEN {a}.EXPORTED   = 0 THEN 'Liberada (não exportada)'
        ELSE 'Exportada (fechada)'
    END"""

SITUACAO_ORCAMENTO = """CASE
        WHEN b.CANCELED          = 1 THEN 'Cancelado'
        WHEN b.AUTHORIZEXTSTATUS = 1 THEN 'Autorizado (operadora)'
        WHEN b.AUTHORIZINTSTATUS = 1 THEN 'Autorizado (interno)'
        WHEN b.LIBERATED         = 1 THEN 'Liberado'
        ELSE 'Pendente'
    END"""

VALOR_ORCAMENTO = """(SELECT NVL(SUM(bi.UNITPRICE * (bi.QUANTITY - NVL(bi.COVERAGEQUANTITY, 0))), 0)
           FROM CAPBUDGETITEM bi WHERE bi.IDBUDGET = b.ID)"""

JOIN_UNIDADE_ORCAMENTO = """JOIN CAPADMISSION a ON a.ID = b.IDADMISSION
LEFT JOIN GLBHEALTHPROVDEP d ON d.ID = a.IDHEALTHPROVDEP
LEFT JOIN GLBHEALTHPROVIDER hp ON hp.ID = d.IDHEALTHPROVIDER"""

SQL_UNIDADES_FATURAM = """
SELECT e.ID        AS id_homecare,
       e.NAME      AS unidade,
       e.FULLNAME  AS razao_social,
       e.IDNUMBER1 AS cnpj
  FROM GLBENTERPRISE e
 WHERE EXISTS (SELECT 1 FROM CAPPAYMENT p WHERE p.IDHOMECARE = e.ID)
 ORDER BY e.NAME
"""

SQL_UNIDADES_CANONICAS = """
SELECT hp.ID             AS id_health_provider,
       hp.NAME           AS unidade_negocio,
       hp.HEALTHCARETYPE AS tipo_assistencia,
       hp.INACTIVE       AS inativa,
       e.ID              AS id_homecare,
       e.NAME            AS empresa_homecare
  FROM GLBHEALTHPROVIDER hp
  LEFT JOIN GLBENTERPRISE e ON e.ID = hp.IDENTERPRISE
 ORDER BY hp.NAME
"""

SQL_CONTAS_POR_STATUS = f"""
WITH contas AS (
    SELECT p.ID, p.IDHOMECARE,
           p.SIMULATION, p.LIBERATED, p.EXPORTED, p.WRITEOFF, p.COLLECTION,
           {CASCATA_SOMA}
      FROM CAPPAYMENT p
      JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
      {JOIN_TIPO_ITEM}
      LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
     WHERE p.STARTDATE >= :DT_INI
       AND p.STARTDATE <  :DT_FIM
       AND {FILTRO_TIPO}
     GROUP BY p.ID, p.IDHOMECARE,
              p.SIMULATION, p.LIBERATED, p.EXPORTED, p.WRITEOFF, p.COLLECTION
), classificadas AS (
    SELECT NVL(hc.NAME, '(sem unidade)') AS unidade,
           {SITUACAO_CONTA.format(a='c')} AS situacao,
           c.*
      FROM contas c
      LEFT JOIN GLBENTERPRISE hc ON hc.ID = c.IDHOMECARE
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

SQL_CONTAS_DETALHE = f"""
SELECT p.ID                                  AS id_conta,
       p.STARTDATE                           AS competencia_inicio,
       p.ENDDATE                             AS competencia_fim,
       NVL(hc.NAME, '(sem unidade)')         AS unidade,
       NVL(op.NAME, '(sem entidade)')        AS operadora,
       {TIPO_PAGADOR}                        AS pagador,
       {SITUACAO_CONTA.format(a='p')}        AS situacao,
       p.LIBERATED, p.EXPORTED, p.WRITEOFF, p.COLLECTION,
       TRIM(p.CLI_PROTOCOENTREGA)            AS protocolo,
       p.CLI_DTENTREGAPROTO                  AS data_entrega,
       p.AUTHORIZEXTCODE                     AS autorizacao_externa,
       {CASCATA_SOMA}
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  {JOIN_TIPO_ITEM}
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY p.ID, p.STARTDATE, p.ENDDATE, hc.NAME, op.NAME, op.CORPORATION,
          p.SIMULATION, p.LIBERATED, p.EXPORTED, p.WRITEOFF, p.COLLECTION,
          p.CLI_PROTOCOENTREGA, p.CLI_DTENTREGAPROTO, p.AUTHORIZEXTCODE
 ORDER BY faturamento_grupo DESC
"""

SQL_ORCAMENTOS_POR_STATUS = f"""
WITH classificados AS (
    SELECT NVL(hp.NAME, '(sem unidade)') AS unidade,
           NVL(hc.NAME, '')              AS empresa_homecare,
           {SITUACAO_ORCAMENTO}          AS situacao,
           {VALOR_ORCAMENTO}             AS valor
      FROM CAPBUDGET b
      {JOIN_UNIDADE_ORCAMENTO}
      LEFT JOIN GLBENTERPRISE hc ON hc.ID = hp.IDENTERPRISE
     WHERE b.STARTDATE >= :DT_INI
       AND b.STARTDATE <  :DT_FIM
   AND (:TIPO IS NULL OR a.ADMISSIONTYPE = :TIPO)
       AND {FILTRO_PROVIDER_OU_HOMECARE}
)
SELECT unidade,
       empresa_homecare,
       situacao,
       COUNT(*)             AS orcamentos,
       ROUND(SUM(valor), 2) AS valor_previsto
  FROM classificados
 GROUP BY unidade, empresa_homecare, situacao
 ORDER BY unidade, valor_previsto DESC
"""

SQL_GAP_RESUMO = f"""
SELECT NVL(hp.NAME, '(sem unidade)')              AS unidade,
       COUNT(*)                                   AS autorizados_sem_faturamento,
       ROUND(SUM({VALOR_ORCAMENTO}), 2)           AS valor_autorizado_pendente
  FROM CAPBUDGET b
  {JOIN_UNIDADE_ORCAMENTO}
 WHERE b.AUTHORIZEXTSTATUS = 1
   AND b.CANCELED = 0
   AND b.STARTDATE >= :DT_INI
   AND b.STARTDATE <  :DT_FIM
   AND (:TIPO IS NULL OR a.ADMISSIONTYPE = :TIPO)
   AND {FILTRO_PROVIDER}
   AND NOT EXISTS (SELECT 1 FROM CAPPAYMENTITEM pi WHERE pi.IDBUDGET = b.ID)
 GROUP BY NVL(hp.NAME, '(sem unidade)')
 ORDER BY valor_autorizado_pendente DESC
"""

SQL_GLOSA_POR_UNIDADE = f"""
SELECT NVL(hc.NAME, '(sem unidade)')                     AS unidade,
       COUNT(*)                                          AS itens,
       COUNT(CASE WHEN i.AUDITBILLVALUE > 0 THEN 1 END)  AS itens_glosados,
       ROUND(SUM({FATURA_OPERADORA}), 2)                 AS fatura_operadora,
       ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2)           AS glosa,
       ROUND(SUM(NVL(i.AUDITBILLSUSTAINED, 0)), 2)       AS glosa_sustentada,
       ROUND(SUM(NVL(i.AUDITBILLRECOVERED, 0)), 2)       AS glosa_recuperada,
       ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)) /
             NULLIF(SUM({FATURA_OPERADORA}), 0) * 100, 2) AS taxa_glosa_pct
  FROM CAPPAYMENTITEM i
  JOIN CAPPAYMENT p ON p.ID = i.IDPAYMENT
  {JOIN_TIPO_ITEM}
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY NVL(hc.NAME, '(sem unidade)')
 ORDER BY glosa DESC
"""

SQL_GLOSA_POR_OPERADORA = f"""
SELECT NVL(op.NAME, '(particular/paciente)')       AS operadora,
       COUNT(*)                                    AS itens_glosados,
       ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2)     AS glosa,
       ROUND(SUM(NVL(i.AUDITBILLSUSTAINED, 0)), 2) AS glosa_sustentada,
       ROUND(SUM(NVL(i.AUDITBILLRECOVERED, 0)), 2) AS glosa_recuperada
  FROM CAPPAYMENTITEM i
  JOIN CAPPAYMENT p ON p.ID = i.IDPAYMENT
  {JOIN_TIPO_ITEM}
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
   AND i.AUDITBILLVALUE > 0
 GROUP BY NVL(op.NAME, '(particular/paciente)')
 ORDER BY glosa DESC
"""

SQL_GLOSA_DETALHE = """
SELECT NVL(hc.NAME, '(sem unidade)')        AS unidade,
       NVL(op.NAME, '(particular)')         AS operadora,
       cat.NAME                             AS categoria_recurso,
       sc.CODENAME                          AS recurso,
       i.QUANTITY                           AS qtd,
       i.AUDITBILLQUANTITY                  AS qtd_glosada,
       ROUND(i.AUDITBILLVALUE, 2)           AS glosa,
       ROUND(NVL(i.AUDITBILLSUSTAINED, 0), 2) AS sustentada,
       ROUND(NVL(i.AUDITBILLRECOVERED, 0), 2) AS recuperada,
       i.AUDITBILLSTATUS                    AS status,
       i.AUDITBILLREASON                    AS cod_recurso,
       i.AUDITBILLCODE                      AS cod_glosa_tiss,
       i.AUDITBILLCOMMENTS                  AS motivo_texto
  FROM CAPPAYMENTITEM i
  JOIN CAPPAYMENT p ON p.ID = i.IDPAYMENT
  LEFT JOIN CAPADMISSION ta ON ta.ID = i.IDADMISSION
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN CTRRESOURCETYPE rt ON rt.RESOURCETYPE = i.RESOURCETYPE
  LEFT JOIN SCCTABLE cat ON cat.ID = rt.IDSCTYPE
  LEFT JOIN SCCCODE sc ON sc.ID = i.SCRESOURCE
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND (:TIPO IS NULL OR ta.ADMISSIONTYPE = :TIPO)
   AND {filtro}
   AND i.AUDITBILLVALUE > 0
 ORDER BY i.AUDITBILLVALUE DESC
""".format(filtro=FILTRO_HOMECARE)

CLASSIFICACAO_MOTIVO = """CASE
        WHEN i.AUDITBILLCOMMENTS IS NULL
          OR REGEXP_LIKE(i.AUDITBILLCOMMENTS, '^[[:space:].;]+$')
            THEN 'Sem narrativa'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%DATA DE CADASTRO%'
            THEN 'Data de cadastro indevida'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%DATA POSTERIOR%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%LIBERA%O DA SENHA%'
            THEN 'Autorização tardia (senha pós-início)'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%SENHA%'
            THEN 'Divergência de senha/autorização'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%DIVERG%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%ATUALIZA% SIST%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%C%DIGO%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%TISS%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%TUSS%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%BRASINDICE%'
            THEN 'Divergência de código'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%UNIDADE DE MEDIDA%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '% LATA%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%GRAMAS%'
            THEN 'Unidade de medida'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%VALIDADE%'
            THEN 'Período de validade'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%CONCESS%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%VISITA%'
            THEN 'Visitas/concessão'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%OR%AMENTO%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%PRORROGA%'
            THEN 'Orçamento/prorrogação'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%CONTRATO%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%NEGOCIA%'
            THEN 'Contrato/negociação'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%LIMINAR%'
            THEN 'Liminar judicial'
        WHEN UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%ANEXO%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%DOCUMENTA%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%GUIA%'
          OR UPPER(NVL(i.AUDITBILLCOMMENTS,' ')) LIKE '%FATURA%'
            THEN 'Documentação/autorização em anexo'
        ELSE 'Outros'
    END"""

SQL_MOTIVOS_TAXONOMIA = f"""
WITH classificados AS (
    SELECT {CLASSIFICACAO_MOTIVO} AS motivo,
           i.AUDITBILLVALUE       AS valor
      FROM CAPPAYMENTITEM i
      JOIN CAPPAYMENT p ON p.ID = i.IDPAYMENT
      {JOIN_TIPO_ITEM}
      LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
     WHERE p.SIMULATION = 0
       AND p.STARTDATE >= :DT_INI
       AND p.STARTDATE <  :DT_FIM
       AND {FILTRO_TIPO}
       AND {FILTRO_HOMECARE}
       AND i.AUDITBILLVALUE > 0
)
SELECT motivo,
       COUNT(*)             AS itens,
       ROUND(SUM(valor), 2) AS valor_glosa
  FROM classificados
 GROUP BY motivo
 ORDER BY valor_glosa DESC
"""

SQL_FATURAMENTO_POR_OPERADORA = f"""
SELECT NVL(hc.NAME, '(sem unidade)')         AS unidade,
       NVL(op.NAME, '(sem entidade)')        AS operadora,
       {TIPO_PAGADOR}                        AS pagador,
       COUNT(DISTINCT p.ID)                  AS contas,
       {CASCATA_SOMA}
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  {JOIN_TIPO_ITEM}
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY NVL(hc.NAME, '(sem unidade)'), NVL(op.NAME, '(sem entidade)'), op.CORPORATION
 ORDER BY faturamento_grupo DESC
"""

SQL_CONTAS_EM_ABERTO = f"""
SELECT NVL(op.NAME, '(sem entidade)')        AS operadora,
       {TIPO_PAGADOR}                        AS pagador,
       COUNT(DISTINCT p.ID)                  AS contas_abertas,
       {CASCATA_SOMA}
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  {JOIN_TIPO_ITEM}
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND p.WRITEOFF = 0
   AND (p.LIBERATED = 0 OR p.EXPORTED = 0)
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY NVL(op.NAME, '(sem entidade)'), op.CORPORATION
 ORDER BY faturamento_grupo DESC
"""

DIMENSOES_CASCATA = {
    "mes": "TO_CHAR(p.STARTDATE, 'YYYY-MM')",
    "unidade": "NVL(hc.NAME, '(sem unidade)')",
    "operadora": "NVL(op.NAME, '(sem entidade)')",
    "pagador": TIPO_PAGADOR,
    # Nunca o nome: o código interno do paciente no ERP (GLBPATIENT.ID)
    "paciente": "CASE WHEN ta.IDPATIENT IS NULL THEN '(sem paciente)' ELSE 'P' || ta.IDPATIENT END",
    "tipo_atendimento": TIPO_ATENDIMENTO,
}

SQL_CASCATA = f"""
SELECT {{dimensao}}                            AS grupo,
       COUNT(DISTINCT p.ID)                  AS contas,
       COUNT(DISTINCT i.IDADMISSION)         AS admissoes,
       {CASCATA_SOMA}
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN CAPADMISSION ta ON ta.ID = i.IDADMISSION
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY {{dimensao}}
 ORDER BY faturamento_grupo DESC
"""

# CAPPAYMENTITEM.PREAUDITBILL{QUANT,VALUE,REASON} e PREAUDITCOMMENTS: o corte que
# a auditoria faz ANTES de a conta ir para a operadora. Motivo: código TISS
# (Tabela 38: 2109, 2009, 1403...) ou código interno 1-4. Preenchido desde
# jul/2024, 7 a 170 itens por mês. Dos 5.414 itens pré-auditados até set/2026,
# 93 tiveram glosa da operadora depois (AUDITBILLVALUE) -- os demais não.
DIMENSOES_PRE_AUDITORIA = {
    "motivo": "NVL(TO_CHAR(i.PREAUDITBILLREASON), '(sem motivo)')",
    "operadora": "NVL(op.NAME, '(sem entidade)')",
    "unidade": "NVL(hc.NAME, '(sem unidade)')",
    "mes": "TO_CHAR(p.STARTDATE, 'YYYY-MM')",
    "tipo_atendimento": TIPO_ATENDIMENTO,
}
FILTRO_PRE_AUDITORIA = "(NVL(i.PREAUDITBILLQUANT, 0) <> 0 OR NVL(i.PREAUDITBILLVALUE, 0) <> 0)"

SQL_PRE_AUDITORIA = f"""
SELECT {{dimensao}}                                      AS grupo,
       COUNT(*)                                        AS itens,
       COUNT(DISTINCT p.ID)                            AS contas,
       ROUND(SUM({PRE_AUDITORIA_ITEM}), 2)             AS pre_auditoria,
       ROUND(SUM(NVL(i.PREAUDITBILLVALUE, 0)), 2)      AS valor_informado,
       SUM(CASE WHEN NVL(i.AUDITBILLVALUE, 0) <> 0 THEN 1 ELSE 0 END) AS itens_glosados_depois,
       ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2)         AS glosa_depois
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN CAPADMISSION ta ON ta.ID = i.IDADMISSION
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_PRE_AUDITORIA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 GROUP BY {{dimensao}}
 ORDER BY pre_auditoria DESC
"""


# Consultas › Pré-auditoria: um item pré-auditado por linha. Não está no MCP.
# Paciente: ID do ERP e código ('P' || ID); o nome só pela revelação sob demanda.
# O comentário do auditor é texto livre e às vezes cita o paciente pelo nome: a
# lista só diz se ele existe; o texto vem item a item (SQL_PRE_AUDITORIA_COMENTARIO).
SQL_PRE_AUDITORIA_ITENS = f"""
SELECT i.ID                                         AS id_item,
       p.ID                                         AS id_conta,
       p.STARTDATE                                  AS competencia,
       NVL(hc.NAME, '(sem unidade)')                AS unidade,
       NVL(op.NAME, '(sem entidade)')               AS operadora,
       ta.ADMISSIONTYPE                             AS tipo,
       i.IDADMISSION                                AS id_admissao,
       ta.IDPATIENT                                 AS id_paciente,
       CASE WHEN ta.IDPATIENT IS NOT NULL THEN 'P' || ta.IDPATIENT END AS paciente_codigo,
       NVL(sc.CODENAME, '(recurso ' || i.SCRESOURCE || ')') AS recurso,
       i.QUANTITY                                   AS quantidade,
       ROUND(i.UNITPRICE, 4)                        AS preco,
       i.PREAUDITBILLQUANT                          AS qtd_pre,
       ROUND({PRE_AUDITORIA_ITEM}, 2)               AS pre_auditoria,
       ROUND(NVL(i.PREAUDITBILLVALUE, 0), 2)        AS valor_informado,
       TO_CHAR(i.PREAUDITBILLREASON)                AS motivo,
       CASE WHEN TRIM(i.PREAUDITCOMMENTS) IS NOT NULL THEN 1 ELSE 0 END AS tem_comentario,
       ROUND(NVL(i.AUDITBILLVALUE, 0), 2)           AS glosa_depois
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN CAPADMISSION ta ON ta.ID = i.IDADMISSION
  LEFT JOIN SCCCODE sc ON sc.ID = i.SCRESOURCE
 WHERE p.SIMULATION = 0
   AND p.STARTDATE >= :DT_INI
   AND p.STARTDATE <  :DT_FIM
   AND {FILTRO_PRE_AUDITORIA}
   AND {FILTRO_TIPO}
   AND {FILTRO_HOMECARE}
 ORDER BY p.STARTDATE DESC, pre_auditoria DESC
"""

SQL_PRE_AUDITORIA_COMENTARIO = """
SELECT TRIM(i.PREAUDITCOMMENTS) AS comentario
  FROM CAPPAYMENTITEM i
 WHERE i.ID = :ID
"""

# Consultas › Conta do paciente: a história de cada paciente dentro da conta --
# orçamento, pré-auditoria, cascata da fatura e glosa. Uma linha por conta ×
# admissão × orçamento: uma conta pode faturar mais de um orçamento do mesmo
# paciente (ex.: conta 86751, orçamentos 247687 de 01 a 13/08 e 247688 de 14 a
# 25/08, os dois autorizados), e cada item aponta para um só (IDBUDGET). Itens
# sem orçamento formam a própria linha. Não está no MCP.
# Nota fiscal no ERP: CAPPAYMENT.BSNUMBER/BSSERIAL (a mesma de FINRECOGBILL, via
# FINRECOGBILLPAYM) existe em ~15% das contas; FINANCIALDOC é texto livre (às
# vezes o nº da nota, às vezes '0' ou 'Posterior'). A planilha de glosa completa.
_CONTA_PACIENTE = f"""
SELECT p.ID                                   AS id_conta,
       p.STARTDATE                            AS competencia,
       TRIM(p.CLI_PROTOCOENTREGA)             AS protocolo,
       p.CLI_DTENTREGAPROTO                   AS data_entrega,
       TRIM(p.BSNUMBER)                       AS nf_numero,
       TRIM(p.BSSERIAL)                       AS nf_serie,
       TRIM(p.FINANCIALDOC)                   AS doc_financeiro,
       {SITUACAO_CONTA.format(a='p')}         AS situacao,
       NVL(hc.NAME, '(sem unidade)')          AS unidade,
       NVL(op.NAME, '(sem entidade)')         AS operadora,
       {TIPO_PAGADOR}                         AS pagador,
       NVL(i.IDADMISSION, 0)                  AS id_admissao,
       ta.ADMISSIONTYPE                       AS tipo,
       ta.IDPATIENT                           AS id_paciente,
       CASE WHEN ta.IDPATIENT IS NOT NULL THEN 'P' || ta.IDPATIENT END AS paciente_codigo,
       i.IDBUDGET                             AS id_orcamento,
       COUNT(*)                               AS itens,
       SUM(CASE WHEN {FILTRO_PRE_AUDITORIA} THEN 1 ELSE 0 END) AS itens_pre_auditados,
       {CASCATA_SOMA},
       ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2)  AS glosa_iw
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
  LEFT JOIN CAPADMISSION ta ON ta.ID = i.IDADMISSION
 WHERE p.SIMULATION = 0
   AND {{filtro}}
 GROUP BY p.ID, p.STARTDATE, p.CLI_PROTOCOENTREGA, p.CLI_DTENTREGAPROTO, p.BSNUMBER, p.BSSERIAL, p.FINANCIALDOC,
          p.SIMULATION, p.WRITEOFF, p.LIBERATED, p.EXPORTED,
          hc.NAME, op.NAME, op.CORPORATION, NVL(i.IDADMISSION, 0), ta.ADMISSIONTYPE, ta.IDPATIENT, i.IDBUDGET
 ORDER BY p.ID, NVL(i.IDADMISSION, 0), i.IDBUDGET NULLS LAST
"""
SQL_CONTA_PACIENTE = _CONTA_PACIENTE.format(
    filtro=f"p.STARTDATE >= :DT_INI AND p.STARTDATE < :DT_FIM AND {FILTRO_TIPO} AND {FILTRO_HOMECARE}")
# Detalhe: uma linha da lista (conta × admissão × orçamento; 0 = sem admissão / sem orçamento)
_FILTRO_LINHA = "p.ID = :ID AND NVL(i.IDADMISSION, 0) = :ADMISSAO AND NVL(i.IDBUDGET, 0) = :ORCAMENTO"
SQL_CONTA_PACIENTE_LINHA = _CONTA_PACIENTE.format(filtro=_FILTRO_LINHA)
# Outros orçamentos do mesmo paciente na mesma conta (links do detalhe)
SQL_CONTA_PACIENTE_IRMAOS = _CONTA_PACIENTE.format(filtro="p.ID = :ID AND NVL(i.IDADMISSION, 0) = :ADMISSAO")

# Itens da fatura de uma linha, com o que a pré-auditoria alterou. Imposto (tipo 15) fora.
SQL_CONTA_PACIENTE_ITENS = f"""
SELECT i.ID                                                AS id_item,
       i.SCRESOURCE                                        AS recurso_id,
       NVL(sc.CODENAME, '(recurso ' || i.SCRESOURCE || ')') AS recurso,
       NVL(cat.NAME, 'tipo ' || i.RESOURCETYPE)            AS categoria,
       i.QUANTITY                                          AS qtd,
       NVL(i.COVERAGEQUANTITY, 0)                          AS qtd_coberta,
       ROUND(i.UNITPRICE, 4)                               AS preco,
       ROUND({COBRADO_ITEM} + {COBERTO_ITEM}, 2)           AS bruto,
       ROUND({PACOTE_ITEM}, 2)                             AS pacote,
       ROUND({PRE_AUDITORIA_ITEM}, 2)                      AS pre_auditoria,
       ROUND({COBRADO_ITEM}, 2)                            AS cobrado,
       ROUND({DESCONTO_ITEM}, 2)                           AS desconto,
       NVL(i.PREAUDITBILLQUANT, 0)                         AS qtd_pre,
       ROUND(NVL(i.PREAUDITBILLVALUE, 0), 2)               AS valor_pre_informado,
       TO_CHAR(i.PREAUDITBILLREASON)                       AS motivo_pre,
       CASE WHEN TRIM(i.PREAUDITCOMMENTS) IS NOT NULL THEN 1 ELSE 0 END AS tem_comentario,
       CASE WHEN {FILTRO_PRE_AUDITORIA} THEN 1 ELSE 0 END  AS alterado_pre,
       ROUND(NVL(i.AUDITBILLVALUE, 0), 2)                  AS glosa_iw,
       i.USERITEM                                          AS item_manual
  FROM CAPPAYMENTITEM i
  LEFT JOIN CTRRESOURCETYPE rt ON rt.RESOURCETYPE = i.RESOURCETYPE
  LEFT JOIN SCCTABLE cat ON cat.ID = rt.IDSCTYPE
  LEFT JOIN SCCCODE sc ON sc.ID = i.SCRESOURCE
 WHERE i.IDPAYMENT = :ID AND NVL(i.IDADMISSION, 0) = :ADMISSAO AND NVL(i.IDBUDGET, 0) = :ORCAMENTO
   AND i.RESOURCETYPE <> 15
 ORDER BY alterado_pre DESC, cobrado DESC
"""

# Valor orçado (mesma regra de VALOR_ORCAMENTO) e situação dos orçamentos citados.
SQL_ORCAMENTOS_VALOR = f"""
SELECT b.ID                                   AS id_orcamento,
       {SITUACAO_ORCAMENTO}                   AS situacao_orcamento,
       b.STARTDATE                            AS orcamento_inicio,
       b.ENDDATE                              AS orcamento_fim,
       ROUND({VALOR_ORCAMENTO}, 2)            AS orcado
  FROM CAPBUDGET b
 WHERE b.ID IN (:IDS)
"""

# XML TISS de volta (src/conciliacao/tiss_cruzamento.py). Não está no MCP.
# Competência, unidade e operadora das contas citadas nos protocolos
SQL_TISS_CONTAS = """
SELECT p.ID AS id_conta, p.STARTDATE AS competencia,
       NVL(hc.NAME, '(sem unidade)') AS unidade, NVL(op.NAME, '(sem entidade)') AS operadora
  FROM CAPPAYMENT p
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.ID IN (:IDS)
"""
# Senha da guia = senha do orçamento
SQL_TISS_ORCAMENTOS_SENHA = """
SELECT b.ID AS id_orcamento, b.IDADMISSION AS id_admissao, TRIM(b.AUTHORIZEXTCODE) AS senha
  FROM CAPBUDGET b
 WHERE TRIM(b.AUTHORIZEXTCODE) IN (:SENHAS)
"""
# Itens cobrados das contas com glosa no XML, para casar o item glosado (quantidade × valor)
SQL_TISS_ITENS_CONTAS = f"""
SELECT i.ID AS id_item, i.IDPAYMENT AS id_conta, NVL(i.IDADMISSION, 0) AS id_admissao,
       i.QUANTITY AS qtd, ROUND(i.UNITPRICE, 4) AS preco, ROUND({COBRADO_ITEM}, 2) AS cobrado,
       NVL(sc.CODENAME, '(recurso ' || i.SCRESOURCE || ')') AS recurso
  FROM CAPPAYMENTITEM i
  LEFT JOIN SCCCODE sc ON sc.ID = i.SCRESOURCE
 WHERE i.IDPAYMENT IN (:IDS) AND i.RESOURCETYPE <> 15 AND {COBRADO_ITEM} <> 0
"""

SQL_AUDITORIA_ULTIMA = f"""
WITH ultima_execucao AS (
    SELECT IDHOMECARE, MAX(TRANSKEY) AS mxt
      FROM TTMPAUDITBILLCTR
     GROUP BY IDHOMECARE
)
SELECT NVL(hc.NAME, '(sem unidade)')                      AS unidade,
       t.INVOICESTATUS                                    AS invoice_status,
       COUNT(*)                                           AS docs,
       ROUND(SUM(t.DOCWVALUE), 2)                         AS declarado,
       ROUND(SUM(NVL(t.RECOGNIZEDVALUE, 0)), 2)           AS reconhecido,
       ROUND(SUM(t.DOCWVALUE - NVL(t.RECOGNIZEDVALUE, 0)), 2) AS nao_reconhecido
  FROM TTMPAUDITBILLCTR t
  JOIN ultima_execucao u ON u.IDHOMECARE = t.IDHOMECARE AND u.mxt = t.TRANSKEY
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = t.IDHOMECARE
 WHERE {FILTRO_HOMECARE}
 GROUP BY NVL(hc.NAME, '(sem unidade)'), t.INVOICESTATUS
 ORDER BY unidade, t.INVOICESTATUS
"""


# Conciliação da planilha de glosa. O protocolo da planilha é
# CAPPAYMENT.CLI_PROTOCOENTREGA (conta de lote, vários pacientes) e cada linha
# da planilha é UMA admissão do paciente nessa conta.
#
# Faturado = SUM(UNITPRICE × (QUANTITY − COVERAGEQUANTITY)). A quantidade
# coberta é o que está incluso no pacote/diária e não é cobrado à parte (e os
# itens de imposto vêm com ela = quantidade, então saem sozinhos). Medido na
# base de set/2026: bate ao centavo em 4.590 de 4.718 linhas casadas; a regra
# antiga (UNITPRICE × QUANTITY sem imposto) batia em 28%. Não está no MCP.
_FATURADO_CONTA = COBRADO_ITEM
# O ERP grava o protocolo com zero à esquerda ('01340288'), tab ('\t1310252')
# e às vezes '-0' onde a planilha tem '_0'. TRIM do Oracle não tira tab.
# Mesma normalização de cruzamento.protocolo_valido.
_PROTOCOLO = ("LTRIM(TRIM(TRANSLATE(p.CLI_PROTOCOENTREGA, '-' || CHR(9) || CHR(10) || CHR(13), "
              "'_   ')), '0')")
_CONCILIACAO = """
SELECT {protocolo}                              AS protocolo,
       p.ID                                      AS id_conta,
       i.IDADMISSION                             AS id_admissao,
       a.IDPATIENT                               AS id_paciente,
       a.ADMISSIONTYPE                           AS tipo_atendimento,
       NVL(hc.NAME, '(sem unidade)')             AS unidade,
       NVL(op.NAME, '(particular/paciente)')     AS operadora,
       pe.NAME                                   AS paciente,
       ROUND(SUM({faturado}), 2)                 AS faturado,
       {glosa}                                   AS glosa_iw
  FROM CAPPAYMENT p
  JOIN {tabela} i ON i.IDPAYMENT = p.ID
  LEFT JOIN CAPADMISSION a ON a.ID = i.IDADMISSION
  LEFT JOIN GLBPATIENT pt ON pt.ID = a.IDPATIENT
  LEFT JOIN GLBPERSON pe ON pe.ID = pt.IDPERSON
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND {protocolo} IN (:PROTOCOLOS)
 GROUP BY {protocolo}, p.ID, i.IDADMISSION, a.IDPATIENT, a.ADMISSIONTYPE, hc.NAME, op.NAME, pe.NAME
"""
SQL_CONCILIACAO_PROTOCOLOS = _CONCILIACAO.format(
    protocolo=_PROTOCOLO, faturado=_FATURADO_CONTA, tabela="CAPPAYMENTITEM", glosa="ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2)")
# Segunda passada: linhas cujo protocolo não achou conta (dois protocolos no
# campo, erro de digitação, "Correios ...", conta sem protocolo no ERP). Casa
# por paciente + competência (mês de CAPPAYMENT.STARTDATE) + valor. Na base de
# set/2026, 213 das 235 linhas sem protocolo achado batem assim.
SQL_CONCILIACAO_COMPETENCIAS = """
SELECT TRUNC(p.STARTDATE, 'MM')                 AS competencia,
       TRIM(p.CLI_PROTOCOENTREGA)                AS protocolo,
       p.ID                                      AS id_conta,
       i.IDADMISSION                             AS id_admissao,
       a.IDPATIENT                               AS id_paciente,
       a.ADMISSIONTYPE                           AS tipo_atendimento,
       NVL(hc.NAME, '(sem unidade)')             AS unidade,
       NVL(op.NAME, '(particular/paciente)')     AS operadora,
       pe.NAME                                   AS paciente,
       ROUND(SUM({faturado}), 2)                 AS faturado,
       ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2)   AS glosa_iw
  FROM CAPPAYMENT p
  JOIN CAPPAYMENTITEM i ON i.IDPAYMENT = p.ID
  JOIN CAPADMISSION a ON a.ID = i.IDADMISSION
  JOIN GLBPATIENT pt ON pt.ID = a.IDPATIENT
  JOIN GLBPERSON pe ON pe.ID = pt.IDPERSON
  LEFT JOIN GLBENTERPRISE hc ON hc.ID = p.IDHOMECARE
  LEFT JOIN GLBENTERPRISE op ON op.ID = p.IDENTERPRISE
 WHERE p.SIMULATION = 0
   AND TRUNC(p.STARTDATE, 'MM') IN (:COMPETENCIAS)
 GROUP BY TRUNC(p.STARTDATE, 'MM'), TRIM(p.CLI_PROTOCOENTREGA), p.ID, i.IDADMISSION, a.IDPATIENT, a.ADMISSIONTYPE, hc.NAME,
          op.NAME, pe.NAME
""".format(faturado=_FATURADO_CONTA)

# Versão de trabalho da conta: em poucos casos (11 na base de set/2026) a
# planilha bate com ela e não com o item final. Não tem coluna de glosa.
SQL_CONCILIACAO_PROTOCOLOS_WORK = _CONCILIACAO.format(
    protocolo=_PROTOCOLO, faturado=_FATURADO_CONTA, tabela="CAPPAYMENTITEMWORK", glosa="0")


# ---- Orçamentos detalhados (relatório orcamentos-detalhe) -- não está no MCP ----
# O orçamento vira a conta: todo item faturado traz CAPPAYMENTITEM.IDBUDGET
# (100% em mai/2026), 1 orçamento = 1 admissão em ~1,2 conta (split). Valor pela
# regra da fatura; paciente só pelo código ('P' || IDPATIENT); operadora pela
# admissão (bate com a da conta em 99,7%).
_ORC_COBRADO = "bi.UNITPRICE * (bi.QUANTITY - NVL(bi.COVERAGEQUANTITY, 0))"
_FAT_COBRADO = "pi.UNITPRICE * (pi.QUANTITY - NVL(pi.COVERAGEQUANTITY, 0))"
_ORCAMENTO = f"""
SELECT b.ID                                   AS id_orcamento,
       b.IDADMISSION                          AS id_admissao,
       a.IDPATIENT                            AS id_paciente,
       a.ADMISSIONTYPE                        AS tipo_atendimento,
       NVL(hp.NAME, '(sem unidade)')          AS unidade,
       NVL(op.NAME, '(sem entidade)')         AS operadora,
       NVL(op.CORPORATION, 0)                 AS particular,
       b.STARTDATE                            AS inicio,
       b.ENDDATE                              AS fim,
       {SITUACAO_ORCAMENTO}                   AS situacao,
       b.AUTHORIZEXTCODE                      AS senha,
       b.AUTHORIZEXTDATEVAL                   AS validade_senha,
       (SELECT COUNT(*) FROM CAPBUDGETITEM bi WHERE bi.IDBUDGET = b.ID AND bi.RESOURCETYPE <> 15) AS itens,
       ROUND((SELECT NVL(SUM({_ORC_COBRADO}), 0) FROM CAPBUDGETITEM bi WHERE bi.IDBUDGET = b.ID), 2) AS orcado,
       ROUND((SELECT NVL(SUM({_FAT_COBRADO}), 0) FROM CAPPAYMENTITEM pi WHERE pi.IDBUDGET = b.ID), 2) AS faturado,
       (SELECT COUNT(DISTINCT pi.IDPAYMENT) FROM CAPPAYMENTITEM pi WHERE pi.IDBUDGET = b.ID) AS contas,
       (SELECT COUNT(DISTINCT p.ID) FROM CAPPAYMENTITEM pi JOIN CAPPAYMENT p ON p.ID = pi.IDPAYMENT
         WHERE pi.IDBUDGET = b.ID AND p.SIMULATION = 0 AND p.WRITEOFF = 0
           AND (p.LIBERATED = 0 OR p.EXPORTED = 0))                                 AS contas_abertas
  FROM CAPBUDGET b
  {JOIN_UNIDADE_ORCAMENTO}
  LEFT JOIN GLBENTERPRISE op ON op.ID = a.IDENTERPRISE
 WHERE {{filtro}}
"""
SQL_ORCAMENTOS_LISTA = _ORCAMENTO.format(
    filtro=f"b.STARTDATE >= :DT_INI AND b.STARTDATE < :DT_FIM AND {FILTRO_PROVIDER} "
           "AND (:TIPO IS NULL OR a.ADMISSIONTYPE = :TIPO)") + " ORDER BY b.STARTDATE DESC"
SQL_ORCAMENTO_CABECALHO = _ORCAMENTO.format(filtro="b.ID = :ID")

_ITENS = """
SELECT i.SCRESOURCE                                        AS recurso_id,
       NVL(sc.CODENAME, '(recurso ' || i.SCRESOURCE || ')') AS recurso,
       NVL(cat.NAME, 'tipo ' || i.RESOURCETYPE)            AS categoria,
       SUM(i.QUANTITY)                                     AS qtd,
       SUM(NVL(i.COVERAGEQUANTITY, 0))                     AS qtd_coberta,
       ROUND(MAX(i.UNITPRICE), 4)                          AS preco,
       ROUND(SUM(i.UNITPRICE * i.QUANTITY), 2)             AS bruto,
       ROUND(SUM(i.UNITPRICE * NVL(i.COVERAGEQUANTITY, 0)), 2) AS pacote,
       ROUND(SUM(i.UNITPRICE * (i.QUANTITY - NVL(i.COVERAGEQUANTITY, 0))), 2) AS cobrado
       {extra}
  FROM {tabela} i
  LEFT JOIN CTRRESOURCETYPE rt ON rt.RESOURCETYPE = i.RESOURCETYPE
  LEFT JOIN SCCTABLE cat ON cat.ID = rt.IDSCTYPE
  LEFT JOIN SCCCODE sc ON sc.ID = i.SCRESOURCE
 WHERE i.IDBUDGET = :ID AND i.RESOURCETYPE <> 15
 GROUP BY i.SCRESOURCE, sc.CODENAME, cat.NAME, i.RESOURCETYPE
 ORDER BY cobrado DESC
"""
SQL_ORCAMENTO_ITENS = _ITENS.format(tabela="CAPBUDGETITEM", extra="")
SQL_ORCAMENTO_FATURADO_ITENS = _ITENS.format(
    tabela="CAPPAYMENTITEM", extra=", ROUND(SUM(NVL(i.AUDITBILLVALUE, 0)), 2) AS glosa_iw")
SQL_ORCAMENTO_CONTAS = f"""
SELECT p.ID                                   AS id_conta,
       {SITUACAO_CONTA.format(a='p')}         AS situacao,
       TRIM(p.CLI_PROTOCOENTREGA)             AS protocolo,
       p.CLI_DTENTREGAPROTO                   AS data_entrega,
       p.STARTDATE                            AS inicio,
       p.ENDDATE                              AS fim,
       ROUND(SUM({_FAT_COBRADO}), 2)          AS cobrado
  FROM CAPPAYMENTITEM pi
  JOIN CAPPAYMENT p ON p.ID = pi.IDPAYMENT
 WHERE pi.IDBUDGET = :ID
 GROUP BY p.ID, p.SIMULATION, p.WRITEOFF, p.LIBERATED, p.EXPORTED, p.CLI_PROTOCOENTREGA, p.CLI_DTENTREGAPROTO,
          p.STARTDATE, p.ENDDATE
 ORDER BY p.ID
"""


# ---- Ocupação (relatório ocupacao e Consultas › Pacientes) -- não está no MCP ----
# "Ocupado" = admissão em atendimento: CAPADMISSION.STATUS = 1 sem data de alta
# (bate com o painel do comercial: Barra 42, Flamengo 41...). STATUS 2 = alta
# (sempre com CHECKOUTDATE); 0/3/4 sem alta são admissões que nunca ficaram
# ativas ou foram canceladas -- não ocupam vaga. Tipo pela admissão
# (0 hospital de transição, 1 home care, 3 ambulatorial); local = setor
# (IDDEPARTMENT -> GLBDEPARTMENT). Leitos não existem no ERP: vêm do parâmetro
# conciliacao.parametro_leitos (Postgres).
_OCUPACAO_BASE = f"""
  FROM CAPADMISSION a
  LEFT JOIN GLBHEALTHPROVDEP d ON d.ID = a.IDHEALTHPROVDEP
  LEFT JOIN GLBHEALTHPROVIDER hp ON hp.ID = d.IDHEALTHPROVIDER
 WHERE a.ADMISSIONTYPE IN (0, 1, 3)
   AND (:TIPO IS NULL OR a.ADMISSIONTYPE = :TIPO)
   AND {FILTRO_PROVIDER}
"""
SQL_OCUPACAO_ATUAL = f"""
SELECT NVL(hp.NAME, '(sem unidade)') AS unidade, a.ADMISSIONTYPE AS tipo,
       COUNT(*) AS ocupados,
       ROUND(AVG(TRUNC(SYSDATE) - TRUNC(a.CHECKINDATE)), 1) AS permanencia_media
  {_OCUPACAO_BASE}
   AND a.STATUS = 1 AND a.CHECKOUTDATE IS NULL
 GROUP BY NVL(hp.NAME, '(sem unidade)'), a.ADMISSIONTYPE
"""
# Censo no fim de cada dia: entrou até o dia e (saiu depois, ou segue em
# atendimento). Só STATUS 1 e 2 -- as que de fato ocuparam vaga.
SQL_OCUPACAO_HISTORICO = f"""
WITH dias AS (
    SELECT TRUNC(:DT_INI) + LEVEL - 1 AS dia FROM dual
    CONNECT BY LEVEL <= TRUNC(:DT_FIM) - TRUNC(:DT_INI)
)
SELECT dias.dia, NVL(hp.NAME, '(sem unidade)') AS unidade, a.ADMISSIONTYPE AS tipo, COUNT(*) AS ocupados
  FROM dias
  JOIN CAPADMISSION a ON a.CHECKINDATE < dias.dia + 1
                     AND (a.CHECKOUTDATE >= dias.dia + 1 OR (a.CHECKOUTDATE IS NULL AND a.STATUS = 1))
                     AND a.STATUS IN (1, 2)
  LEFT JOIN GLBHEALTHPROVDEP d ON d.ID = a.IDHEALTHPROVDEP
  LEFT JOIN GLBHEALTHPROVIDER hp ON hp.ID = d.IDHEALTHPROVIDER
 WHERE a.ADMISSIONTYPE IN (0, 1, 3)
   AND (:TIPO IS NULL OR a.ADMISSIONTYPE = :TIPO)
   AND {FILTRO_PROVIDER}
 GROUP BY dias.dia, NVL(hp.NAME, '(sem unidade)'), a.ADMISSIONTYPE
 ORDER BY dias.dia
"""
SQL_PACIENTES_EM_ATENDIMENTO = f"""
SELECT a.ID                                   AS id_admissao,
       a.IDPATIENT                            AS id_paciente,
       'P' || a.IDPATIENT                     AS paciente_codigo,
       NVL(hp.NAME, '(sem unidade)')          AS unidade,
       a.ADMISSIONTYPE                        AS tipo,
       NVL(dep.NAME, '(sem setor)')           AS setor,
       a.CHECKINDATE                          AS entrada,
       TRUNC(SYSDATE) - TRUNC(a.CHECKINDATE)  AS dias,
       NVL(op.NAME, '(sem entidade)')         AS operadora
  FROM CAPADMISSION a
  LEFT JOIN GLBHEALTHPROVDEP d ON d.ID = a.IDHEALTHPROVDEP
  LEFT JOIN GLBHEALTHPROVIDER hp ON hp.ID = d.IDHEALTHPROVIDER
  LEFT JOIN GLBDEPARTMENT dep ON dep.ID = a.IDDEPARTMENT
  LEFT JOIN GLBENTERPRISE op ON op.ID = a.IDENTERPRISE
 WHERE a.STATUS = 1 AND a.CHECKOUTDATE IS NULL
   AND a.ADMISSIONTYPE IN (0, 1, 3)
   AND (:TIPO IS NULL OR a.ADMISSIONTYPE = :TIPO)
   AND {FILTRO_PROVIDER}
 ORDER BY hp.NAME, a.CHECKINDATE
"""


# Nome estável -> SQL. É o contrato com os blocos (e com o futuro sql_bq.py).
# Nome do paciente, só para a revelação sob demanda (privacidade.nome_paciente).
# Não está no MCP.
SQL_PACIENTE_NOME = """
SELECT pe.NAME AS nome
  FROM GLBPATIENT pt
  JOIN GLBPERSON pe ON pe.ID = pt.IDPERSON
 WHERE pt.ID = :ID
"""

CONSULTAS = {
    "paciente_nome": SQL_PACIENTE_NOME,
    "unidades_faturam": SQL_UNIDADES_FATURAM,
    "unidades_canonicas": SQL_UNIDADES_CANONICAS,
    "contas_por_status": SQL_CONTAS_POR_STATUS,
    "contas_detalhe": SQL_CONTAS_DETALHE,
    "faturamento_por_operadora": SQL_FATURAMENTO_POR_OPERADORA,
    "contas_em_aberto": SQL_CONTAS_EM_ABERTO,
    "orcamentos_por_status": SQL_ORCAMENTOS_POR_STATUS,
    "gap_resumo": SQL_GAP_RESUMO,
    "glosa_por_unidade": SQL_GLOSA_POR_UNIDADE,
    "glosa_por_operadora": SQL_GLOSA_POR_OPERADORA,
    "glosa_detalhe": SQL_GLOSA_DETALHE,
    "motivos_taxonomia": SQL_MOTIVOS_TAXONOMIA,
    "auditoria_ultima": SQL_AUDITORIA_ULTIMA,
    "cascata_por_pagador": SQL_CASCATA.replace("{dimensao}", DIMENSOES_CASCATA["pagador"]),
    "cascata_por_mes": SQL_CASCATA.replace("{dimensao}", DIMENSOES_CASCATA["mes"]),
    "cascata_por_operadora": SQL_CASCATA.replace("{dimensao}", DIMENSOES_CASCATA["operadora"]),
    "pre_auditoria_por_motivo": SQL_PRE_AUDITORIA.replace("{dimensao}", DIMENSOES_PRE_AUDITORIA["motivo"]),
    "pre_auditoria_por_operadora": SQL_PRE_AUDITORIA.replace("{dimensao}", DIMENSOES_PRE_AUDITORIA["operadora"]),
    "pre_auditoria_por_mes": SQL_PRE_AUDITORIA.replace("{dimensao}", DIMENSOES_PRE_AUDITORIA["mes"]),
    "pre_auditoria_itens": SQL_PRE_AUDITORIA_ITENS,
    "pre_auditoria_comentario": SQL_PRE_AUDITORIA_COMENTARIO,
    "conta_paciente": SQL_CONTA_PACIENTE,
    "tiss_contas": SQL_TISS_CONTAS,
    "tiss_orcamentos_senha": SQL_TISS_ORCAMENTOS_SENHA,
    "tiss_itens_contas": SQL_TISS_ITENS_CONTAS,
    "conta_paciente_linha": SQL_CONTA_PACIENTE_LINHA,
    "conta_paciente_irmaos": SQL_CONTA_PACIENTE_IRMAOS,
    "conta_paciente_itens": SQL_CONTA_PACIENTE_ITENS,
    "orcamentos_valor": SQL_ORCAMENTOS_VALOR,
    "conciliacao_protocolos": SQL_CONCILIACAO_PROTOCOLOS,
    "conciliacao_protocolos_work": SQL_CONCILIACAO_PROTOCOLOS_WORK,
    "conciliacao_competencias": SQL_CONCILIACAO_COMPETENCIAS,
    "orcamentos_lista": SQL_ORCAMENTOS_LISTA,
    "orcamento_cabecalho": SQL_ORCAMENTO_CABECALHO,
    "orcamento_itens": SQL_ORCAMENTO_ITENS,
    "orcamento_faturado_itens": SQL_ORCAMENTO_FATURADO_ITENS,
    "orcamento_contas": SQL_ORCAMENTO_CONTAS,
    "ocupacao_atual": SQL_OCUPACAO_ATUAL,
    "ocupacao_historico": SQL_OCUPACAO_HISTORICO,
    "pacientes_em_atendimento": SQL_PACIENTES_EM_ATENDIMENTO,
}
