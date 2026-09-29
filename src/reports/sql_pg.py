"""SQLs dos blocos de Glosa Planilha, sobre a carga ativa da Conciliação (Postgres).

Mesmo contrato de sql_oracle.py: os blocos pedem pelo nome, fonte.rodar decide
o banco. Binds nomeados do psycopg: %(DT_INI)s, %(DT_FIM)s (fim exclusivo),
%(UNIDADE)s ("EMPRESA · FILIAL") e %(CONVENIO)s; NULL = sem filtro.
Na migração para o BigQuery, estas consultas viram views sobre a tabela carregada.

Faturado vem do ORACLE (conciliacao.cruzamento.faturado_erp, uma vez por
admissão); o VALOR FATURADO da planilha só entra como conferência
(faturado_planilha). Da planilha vêm apenas glosa e recebimento, que o ERP
não registra mais.

Glosa: as consultas leem conciliacao.glosa_efetiva e cruzamento_efetivo (schema
v10). Onde a admissão tem o XML TISS de volta da operadora, glosa e motivo vêm
do XML (origem_glosa = 'xml'); recurso, recuperado e perda seguem da planilha.
Glosa que só está no XML entra como linha sintética (linha negativa).
"""

# Paciente só por código (privacidade.SQL_CODIGO), nunca pelo nome.
PACIENTE = "COALESCE('P' || x.id_paciente::text, g.paciente_codigo)"

# Linhas da carga ativa dentro do recorte. `c` traz a data de referência (o HOJE).
_BASE = """
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  LEFT JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE (%(DT_INI)s::date IS NULL OR g.competencia >= %(DT_INI)s::date)
   AND (%(DT_FIM)s::date IS NULL OR g.competencia <  %(DT_FIM)s::date)
   AND (%(UNIDADE)s::text IS NULL OR g.empresa || ' · ' || g.filial = %(UNIDADE)s::text)
   AND (%(CONVENIO)s::text IS NULL OR g.convenio = %(CONVENIO)s::text)
   AND (%(MOTIVO)s::text IS NULL OR g.motivo = %(MOTIVO)s::text)
   AND (%(TIPO)s::int IS NULL OR x.tipo_atendimento = %(TIPO)s::int)
"""

_SOMAS = """
       COUNT(*)                                   AS linhas,
       COALESCE(SUM(x.faturado_erp) FILTER (WHERE x.principal), 0) AS faturado,
       COALESCE(SUM(g.valor_faturado), 0)         AS faturado_planilha,
       COUNT(*) FILTER (WHERE x.situacao = 'CONCILIADO') AS conciliadas,
       COALESCE(SUM(g.glosa), 0)                  AS glosa,
       COALESCE(SUM(g.glosa) FILTER (WHERE g.origem_glosa = 'xml'), 0) AS glosa_xml,
       COALESCE(SUM(g.valor_recursado), 0)        AS recursado,
       COALESCE(SUM(g.glosa_acatada), 0)          AS acatada,
       COALESCE(SUM(g.valor_recurso_bruto), 0)    AS recuperado_bruto,
       COALESCE(SUM(g.valor_recurso_liquido), 0)  AS recuperado,
       COALESCE(SUM(g.glosa_mantida), 0)          AS mantida"""

CONSULTAS = {
    "gp_totais": f"""
SELECT {_SOMAS},
       COUNT(*) FILTER (WHERE g.status_glosa = 'ANÁLISE OPALUS')                     AS sem_recurso,
       COALESCE(SUM(g.glosa) FILTER (WHERE g.status_glosa = 'ANÁLISE OPALUS'), 0)   AS glosa_sem_recurso,
       COALESCE(SUM(g.glosa) FILTER (WHERE g.status_glosa = 'ANÁLISE OPALUS'
                                       AND g.prazo_recurso < c.data_referencia), 0) AS glosa_prazo_vencido
  {_BASE}
 GROUP BY c.data_referencia
""",
    "gp_por_competencia": f"""
SELECT g.competencia, {_SOMAS}
  {_BASE}
 GROUP BY g.competencia ORDER BY g.competencia
""",
    "gp_por_status": f"""
SELECT COALESCE(g.status_glosa, '(sem status)') AS status_glosa, {_SOMAS}
  {_BASE}
 GROUP BY 1
""",
    "gp_por_convenio": f"""
SELECT g.convenio, {_SOMAS}
  {_BASE}
 GROUP BY g.convenio ORDER BY glosa DESC
""",
    "gp_por_classificacao": f"""
SELECT COALESCE(g.classificacao, '(sem classificação)') AS classificacao, {_SOMAS}
  {_BASE}
 GROUP BY 1 ORDER BY glosa DESC
""",
    "gp_por_motivo": f"""
SELECT COALESCE(g.motivo, '(sem código)') AS motivo, MAX(m.descricao) AS descricao, BOOL_OR(m.vigente) AS vigente,
       MODE() WITHIN GROUP (ORDER BY g.classificacao) AS classificacao, {_SOMAS}
  {_BASE.replace("WHERE", "LEFT JOIN conciliacao.motivo_tiss m ON m.codigo = g.motivo WHERE", 1)}
 GROUP BY 1 ORDER BY glosa DESC
""",
    "gp_por_unidade": f"""
SELECT g.empresa, g.filial, {_SOMAS}
  {_BASE}
 GROUP BY g.empresa, g.filial ORDER BY glosa DESC
""",
    # Glosa ainda sem recurso (ANÁLISE OPALUS): quanto tempo falta para o prazo
    "gp_prazo_faixas": f"""
SELECT CASE WHEN g.prazo_recurso IS NULL THEN 'sem prazo'
            WHEN g.prazo_recurso <  c.data_referencia THEN 'vencido'
            WHEN g.prazo_recurso <= c.data_referencia + 7 THEN 'até 7 dias'
            WHEN g.prazo_recurso <= c.data_referencia + 15 THEN '8 a 15 dias'
            WHEN g.prazo_recurso <= c.data_referencia + 30 THEN '16 a 30 dias'
            ELSE 'mais de 30 dias' END AS faixa,
       COUNT(*) AS linhas, COALESCE(SUM(g.glosa), 0) AS glosa
  {_BASE}
   AND g.status_glosa = 'ANÁLISE OPALUS'
 GROUP BY 1
""",
    # Cascata até o saldo a receber. Só linhas casadas com o ERP (senão não há
    # fatura para abrir a cascata). Retenção = alíquota da premissa do convênio
    # (g.imposto) sobre a fatura; perda = acatada + mantida, líquidas de retenção.
    "gp_cascata": f"""
SELECT COUNT(*)                                                                  AS linhas,
       COUNT(*) FILTER (WHERE x.faturado_erp IS NULL)                            AS sem_erp,
       COALESCE(SUM(g.valor_faturado) FILTER (WHERE x.faturado_erp IS NULL), 0)  AS faturado_sem_erp,
       COALESCE(SUM(x.faturado_erp) FILTER (WHERE x.principal), 0)               AS fatura,
       COALESCE(SUM(x.faturado_erp * COALESCE(g.imposto, 0))
                FILTER (WHERE x.principal), 0)                                   AS retencao,
       COALESCE(SUM(g.valor_recebido) FILTER (WHERE x.faturado_erp IS NOT NULL), 0) AS recebido,
       COALESCE(SUM(g.valor_recurso_liquido) FILTER (WHERE x.faturado_erp IS NOT NULL), 0) AS recurso,
       COALESCE(SUM((COALESCE(g.glosa_acatada, 0) + COALESCE(g.glosa_mantida, 0))
                    * (1 - COALESCE(g.imposto, 0))) FILTER (WHERE x.faturado_erp IS NOT NULL), 0) AS perda
  {_BASE}
""",
    # ---- Motivos de glosa (relatório glosa-motivos) ----
    "gm_convenio_motivo": f"""
SELECT g.convenio, COALESCE(g.motivo, '(sem código)') AS motivo, COUNT(*) AS linhas,
       COALESCE(SUM(g.glosa), 0) AS glosa
  {_BASE}
 GROUP BY g.convenio, COALESCE(g.motivo, '(sem código)')
""",
    "gm_evolucao": f"""
SELECT g.competencia, COALESCE(g.motivo, '(sem código)') AS motivo, COALESCE(SUM(g.glosa), 0) AS glosa
  {_BASE}
   AND g.competencia IS NOT NULL
 GROUP BY g.competencia, COALESCE(g.motivo, '(sem código)')
 ORDER BY g.competencia
""",
    "gm_motivos": """
SELECT COALESCE(g.motivo, '(sem código)') AS motivo, MAX(m.descricao) AS descricao, COUNT(*) AS linhas
  FROM conciliacao.glosa_efetiva g JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  LEFT JOIN conciliacao.motivo_tiss m ON m.codigo = g.motivo
 GROUP BY 1 ORDER BY COUNT(*) DESC
""",
    # ---- Orçamentos detalhados: glosa da planilha pela admissão do orçamento ----
    "orc_glosa_admissoes": """
SELECT x.id_admissao, g.competencia, COUNT(*) AS linhas, COALESCE(SUM(g.glosa), 0) AS glosa,
       MODE() WITHIN GROUP (ORDER BY g.motivo) AS motivo
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE x.id_admissao = ANY(%(ADMISSOES)s::bigint[])
 GROUP BY x.id_admissao, g.competencia
""",
    "orc_glosa_linhas": f"""
SELECT g.competencia, g.motivo, m.descricao, m.vigente, g.classificacao, g.glosa, g.valor_recursado,
       g.valor_recurso_bruto AS recuperado, COALESCE(g.glosa_acatada, 0) + COALESCE(g.glosa_mantida, 0) AS perda,
       g.status_glosa, g.prazo_recurso, g.protocolo, {PACIENTE} AS paciente_codigo
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
  LEFT JOIN conciliacao.motivo_tiss m ON m.codigo = g.motivo
 WHERE x.id_admissao = %(ADMISSAO)s::bigint
   AND g.competencia >= %(DT_INI)s::date AND g.competencia < %(DT_FIM)s::date
 ORDER BY g.glosa DESC
""",
    # Glosa da planilha por operadora (nome do ERP) no período e motivo mais frequente.
    # O denominador da taxa vem do Oracle (fatura da operadora no mesmo período):
    # a planilha só tem as contas que tiveram glosa.
    "orc_glosa_operadora": """
SELECT x.operadora_erp AS operadora, COALESCE(SUM(g.glosa), 0) AS glosa,
       MODE() WITHIN GROUP (ORDER BY g.motivo) AS motivo
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE x.operadora_erp IS NOT NULL
   AND g.competencia >= %(DT_INI)s::date AND g.competencia < %(DT_FIM)s::date
 GROUP BY x.operadora_erp
""",
    "orc_hist_operadora": """
SELECT g.motivo, MAX(m.descricao) AS descricao, COUNT(*) AS linhas, COALESCE(SUM(g.glosa), 0) AS glosa,
       COALESCE(SUM(g.valor_recurso_bruto), 0) AS recuperado,
       COALESCE(SUM(COALESCE(g.glosa_acatada, 0) + COALESCE(g.glosa_mantida, 0)), 0) AS perda,
       MODE() WITHIN GROUP (ORDER BY g.classificacao) AS classificacao
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
  LEFT JOIN conciliacao.motivo_tiss m ON m.codigo = g.motivo
 WHERE x.operadora_erp = %(OPERADORA)s
 GROUP BY g.motivo ORDER BY glosa DESC LIMIT 10
""",
    "orc_pacientes_glosados": """
SELECT x.id_paciente, COUNT(*) AS linhas, COALESCE(SUM(g.glosa), 0) AS glosa
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE x.id_paciente IS NOT NULL AND g.glosa > 0
 GROUP BY x.id_paciente
""",
    # ---- Consultas › Glosas (linha a linha) ----
    "cs_glosas": f"""
SELECT g.linha, g.competencia, g.empresa || ' · ' || g.filial AS unidade, g.convenio,
       x.id_paciente, {PACIENTE} AS paciente_codigo, g.protocolo, g.motivo, m.descricao AS motivo_descricao,
       g.classificacao,
       g.glosa, g.valor_recursado, g.valor_recurso_bruto AS recuperado,
       COALESCE(g.glosa_acatada, 0) + COALESCE(g.glosa_mantida, 0) AS perda,
       g.status_glosa, g.prazo_recurso, (g.prazo_recurso - c.data_referencia) AS dias_recurso,
       x.situacao, x.regra, g.valor_faturado, x.faturado_erp, x.diferenca, x.id_conta,
       g.origem_glosa, g.motivos_xml, g.motivo_planilha, g.glosa_planilha,
       CASE x.tipo_atendimento WHEN 0 THEN 'Hospital de transição' WHEN 1 THEN 'Home care'
            WHEN 3 THEN 'Ambulatorial' END AS tipo_atendimento
  {_BASE.replace("WHERE", "LEFT JOIN conciliacao.motivo_tiss m ON m.codigo = g.motivo WHERE", 1)}
   AND (%(STATUS)s::text IS NULL OR g.status_glosa = %(STATUS)s::text)
   AND (%(SITUACAO)s::text IS NULL OR x.situacao = %(SITUACAO)s::text)
   AND (%(ORIGEM)s::text IS NULL OR g.origem_glosa = %(ORIGEM)s::text)
   AND (%(PRAZO)s::text IS NULL OR (g.status_glosa = 'ANÁLISE OPALUS' AND
        CASE WHEN g.prazo_recurso IS NULL THEN 'sem prazo'
             WHEN g.prazo_recurso <  c.data_referencia THEN 'vencido'
             WHEN g.prazo_recurso <= c.data_referencia + 7 THEN 'até 7 dias'
             WHEN g.prazo_recurso <= c.data_referencia + 15 THEN '8 a 15 dias'
             WHEN g.prazo_recurso <= c.data_referencia + 30 THEN '16 a 30 dias'
             ELSE 'mais de 30 dias' END = %(PRAZO)s::text))
 ORDER BY g.glosa DESC NULLS LAST
""",
    # Leitos vigentes hoje por unidade (parâmetro; a vigência mais recente até hoje)
    # Consultas › Conta do paciente: glosa da planilha por conta × admissão (carga ativa).
    # Linha casada pelo total do paciente fica sem admissão: vem com o id_paciente.
    "cp_glosas": """
SELECT x.id_conta, x.id_admissao, x.id_paciente,
       COUNT(*)                                                  AS linhas_planilha,
       COALESCE(SUM(g.valor_faturado), 0)                        AS faturado_planilha,
       COALESCE(SUM(g.glosa), 0)                                 AS glosa,
       COALESCE(SUM(g.valor_recurso_bruto), 0)                   AS recuperado,
       COALESCE(SUM(COALESCE(g.glosa_acatada, 0) + COALESCE(g.glosa_mantida, 0)), 0) AS perda,
       string_agg(DISTINCT g.motivo, ', ')                       AS motivos,
       string_agg(DISTINCT g.status_glosa, ', ')                 AS status_glosa,
       string_agg(DISTINCT x.situacao, ', ')                     AS situacao_cruzamento,
       string_agg(DISTINCT NULLIF(TRIM(g.nota_fiscal), ''), ', ') AS notas_planilha,
       string_agg(DISTINCT g.origem_glosa, '/')                  AS origem_glosa
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
 WHERE x.id_conta = ANY(%(CONTAS)s)
 GROUP BY x.id_conta, x.id_admissao, x.id_paciente
""",
    # Detalhe da conta do paciente: as linhas da planilha dessa admissão na conta
    "cp_glosa_linhas": """
SELECT g.linha, g.competencia, g.motivo, m.descricao, m.vigente, g.classificacao, g.glosa, g.valor_recursado,
       g.valor_recurso_bruto AS recuperado, COALESCE(g.glosa_acatada, 0) + COALESCE(g.glosa_mantida, 0) AS perda,
       g.status_glosa, g.prazo_recurso, g.protocolo, NULLIF(TRIM(g.nota_fiscal), '') AS nota_fiscal,
       g.valor_faturado, x.situacao, x.regra, g.origem_glosa, g.motivos_xml, g.motivo_planilha, g.glosa_planilha
  FROM conciliacao.glosa_efetiva g
  JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
  JOIN conciliacao.cruzamento_efetivo x ON x.carga_id = g.carga_id AND x.linha = g.linha
  LEFT JOIN conciliacao.motivo_tiss m ON m.codigo = g.motivo
 WHERE x.id_conta = %(CONTA)s::bigint
   AND (x.id_admissao = %(ADMISSAO)s::bigint OR (x.id_admissao IS NULL AND x.id_paciente = %(PACIENTE)s::bigint))
 ORDER BY g.glosa DESC
""",
    # Detalhe da conta do paciente: o retorno da operadora (XML TISS de volta) dessa admissão
    "cp_tiss_guias": """
SELECT g.id, g.protocolo, g.guia_prestador, g.guia_operadora, g.situacao, g.regra, g.informado, g.processado,
       g.liberado, g.glosa, g.motivo_principal, g.motivos, g.operadora_nome, g.data_emissao, g.numero_demonstrativo
  FROM conciliacao.tiss_guia_ativa g
 WHERE g.id_conta = %(CONTA)s::bigint AND g.id_admissao = %(ADMISSAO)s::bigint
""",
    "cp_tiss_itens": """
SELECT i.sequencial, i.data, i.tabela, i.codigo, i.descricao, i.quantidade, i.informado, i.processado, i.liberado,
       i.glosa, i.motivo_principal, i.motivos, i.id_item_erp
  FROM conciliacao.tiss_item i
  JOIN conciliacao.tiss_guia_ativa g ON g.id = i.guia_id
 WHERE g.id_conta = %(CONTA)s::bigint AND g.id_admissao = %(ADMISSAO)s::bigint AND i.glosa > 0
 ORDER BY i.glosa DESC
""",
    # Descrição do motivo da pré-auditoria: internos (1-4, parâmetro) e TISS (Tabela 38)
    "pa_motivos": """
SELECT codigo, descricao, 'interno' AS origem FROM conciliacao.motivo_preauditoria
UNION ALL
SELECT codigo, descricao, 'tiss' AS origem FROM conciliacao.motivo_tiss
 WHERE codigo NOT IN (SELECT codigo FROM conciliacao.motivo_preauditoria)
""",
    "oc_leitos": """
SELECT DISTINCT ON (unidade, tipo_atendimento) unidade, tipo_atendimento, leitos, vigente_desde
  FROM conciliacao.parametro_leitos
 WHERE vigente_desde <= CURRENT_DATE
 ORDER BY unidade, tipo_atendimento, vigente_desde DESC
""",
    "gp_unidades": """
SELECT DISTINCT g.empresa || ' · ' || g.filial AS unidade
  FROM conciliacao.glosa_linha g JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
 ORDER BY 1
""",
    "gp_convenios": """
SELECT DISTINCT g.convenio
  FROM conciliacao.glosa_linha g JOIN conciliacao.carga c ON c.id = g.carga_id AND c.ativa AND c.tipo = 'glosa'
 WHERE g.convenio IS NOT NULL ORDER BY 1
""",
}
