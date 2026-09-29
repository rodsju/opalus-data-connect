-- Conciliação: base de glosa carregada por CSV (substitui a glosa do IW, parada
-- desde jul/2025) e as premissas da planilha. Idempotente: roda em todo boot
-- de página de conciliação (src/conciliacao/banco.py) e por `make conciliacao ARGS=schema`.
-- Coluna nova: some na CREATE e repita num ALTER ... ADD COLUMN IF NOT EXISTS no fim.

CREATE SCHEMA IF NOT EXISTS conciliacao;

-- Premissas (uma tabela por tabela nomeada do base_glosa.xlsx) -------------
CREATE TABLE IF NOT EXISTS conciliacao.premissa_imposto (
    empresa       text NOT NULL,
    convenio      text NOT NULL,
    imposto       numeric,
    data_alt1     date,
    imposto_alt1  numeric,
    data_alt2     date,
    imposto_alt2  numeric
);

CREATE TABLE IF NOT EXISTS conciliacao.premissa_prazo (
    convenio text NOT NULL,
    prazo    integer
);

CREATE TABLE IF NOT EXISTS conciliacao.premissa_recurso (
    convenio       text NOT NULL,
    prazo_recurso  integer,
    previsao_pagto integer,
    como_recursar  text,
    obs            text
);

CREATE TABLE IF NOT EXISTS conciliacao.convenio_de_para (
    empresa          text NOT NULL,
    convenio         text NOT NULL,
    convenio_formula text NOT NULL
);

CREATE TABLE IF NOT EXISTS conciliacao.aging_faixa (
    dia   integer NOT NULL,
    grupo text NOT NULL
);

CREATE TABLE IF NOT EXISTS conciliacao.empresa_convenio (
    empresa      text NOT NULL,
    filial       text,
    convenio     text NOT NULL,
    categoria_nf text,
    cnpj         text
);

CREATE TABLE IF NOT EXISTS conciliacao.motivo_tiss (
    codigo    text NOT NULL,
    descricao text
);

-- Cargas -------------------------------------------------------------------
-- Cada upload é uma foto completa da planilha. Só uma fica ativa; as outras
-- ficam para comparar o que mudou.
CREATE TABLE IF NOT EXISTS conciliacao.carga (
    id              bigserial PRIMARY KEY,
    tipo            text NOT NULL DEFAULT 'glosa',
    arquivo         text NOT NULL,
    sha256          text NOT NULL,
    autor           text,
    criada_em       timestamptz NOT NULL DEFAULT now(),
    data_referencia date NOT NULL,
    linhas          integer NOT NULL DEFAULT 0,
    rejeitadas      integer NOT NULL DEFAULT 0,
    ativa           boolean NOT NULL DEFAULT false,
    relatorio       jsonb NOT NULL DEFAULT '{}'::jsonb,
    cruzada_em      timestamptz,
    cruzamento      jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS carga_uma_ativa ON conciliacao.carga (tipo) WHERE ativa;

CREATE TABLE IF NOT EXISTS conciliacao.glosa_linha (
    carga_id                  bigint NOT NULL REFERENCES conciliacao.carga (id) ON DELETE CASCADE,
    linha                     integer NOT NULL,
    -- digitadas
    empresa                   text,
    filial                    text,
    convenio                  text,
    paciente                  text,
    mod                       text,
    periodo                   text,
    protocolo                 text,
    valor_faturado            numeric,
    data_entrega              date,
    data_prevista_recebimento date,
    nota_fiscal               text,
    glosa                     numeric,
    valor_recebido            numeric,
    data_recebimento          date,
    obs_financeiro            text,
    devolucao                 date,
    data_reapresentacao       date,
    protocolo_reapresentacao  text,
    motivo                    text,
    classificacao_bruta       text,
    valor_recursado           numeric,
    data_recurso              date,
    protocolo_recurso         text,
    previsao_pagto_recurso    date,
    glosa_acatada             numeric,
    data_receb_recurso        date,
    valor_recurso_bruto       numeric,
    valor_recurso_liquido     numeric,
    glosa_mantida             numeric,
    nf_recurso                text,
    observacao                text,
    banco                     text,
    -- calculadas pelo app (src/conciliacao/regras.py)
    convenio_formula          text,
    convenio_formula_de_para  text,
    convenio_formula_manual   boolean,
    competencia               date,
    prazo                     integer,
    data_contratual           date,
    mes_previsao              date,
    imposto                   numeric,
    valor_liquido             numeric,
    base_calculo_1            numeric,
    base_calculo_2            numeric,
    status                    text,
    dias_atraso               integer,
    aging                     text,
    classificacao             text,
    status_glosa              text,
    prazo_recurso             date,
    pendencias                text[],
    divergencias              text[],
    -- o que a planilha trouxe nas colunas de fórmula (para comparar)
    planilha                  jsonb,
    PRIMARY KEY (carga_id, linha)
);

CREATE INDEX IF NOT EXISTS glosa_linha_competencia ON conciliacao.glosa_linha (carga_id, competencia);
CREATE INDEX IF NOT EXISTS glosa_linha_protocolo ON conciliacao.glosa_linha (carga_id, protocolo);

-- Cruzamento com o ERP (uma linha por linha da carga) ------------------------
CREATE TABLE IF NOT EXISTS conciliacao.cruzamento (
    carga_id        bigint NOT NULL REFERENCES conciliacao.carga (id) ON DELETE CASCADE,
    linha           integer NOT NULL,
    situacao        text NOT NULL,
    id_conta        bigint,
    unidade_erp     text,
    operadora_erp   text,
    faturado_erp    numeric,
    glosa_iw        numeric,
    diferenca       numeric,
    -- Primeira linha do par protocolo + paciente: faturado_erp e glosa_iw são
    -- do par inteiro e só somam nela, senão contariam uma vez por linha.
    principal       boolean NOT NULL DEFAULT true,
    PRIMARY KEY (carga_id, linha)
);

-- v2: casamento por admissão (cada linha da planilha é uma admissão da conta)
ALTER TABLE conciliacao.cruzamento ADD COLUMN IF NOT EXISTS id_admissao bigint;
ALTER TABLE conciliacao.cruzamento ADD COLUMN IF NOT EXISTS regra text;
ALTER TABLE conciliacao.cruzamento ADD COLUMN IF NOT EXISTS protocolo_erp text;

-- v3: Tabela 38 TISS sincronizada da ANS (src/conciliacao/tiss.py)
ALTER TABLE conciliacao.motivo_tiss ADD COLUMN IF NOT EXISTS inicio_vigencia date;
ALTER TABLE conciliacao.motivo_tiss ADD COLUMN IF NOT EXISTS fim_vigencia date;
ALTER TABLE conciliacao.motivo_tiss ADD COLUMN IF NOT EXISTS fim_implantacao date;

CREATE TABLE IF NOT EXISTS conciliacao.sincronizacao (
    id           bigserial PRIMARY KEY,
    fonte        text NOT NULL,
    versao       text,
    url          text,
    autor        text,
    executada_em timestamptz NOT NULL DEFAULT now(),
    linhas       integer,
    detalhes     jsonb
);
ALTER TABLE conciliacao.motivo_tiss ADD COLUMN IF NOT EXISTS vigente boolean;
ALTER TABLE conciliacao.motivo_tiss ADD COLUMN IF NOT EXISTS versao text;

-- v4: paciente nunca é exibido pelo nome (src/conciliacao/privacidade.py)
ALTER TABLE conciliacao.glosa_linha ADD COLUMN IF NOT EXISTS paciente_codigo text;
ALTER TABLE conciliacao.cruzamento ADD COLUMN IF NOT EXISTS id_paciente bigint;

-- v5: análise de orçamento por IA (src/reports/orcamento_ia.py). Sem nome de paciente no payload.
CREATE TABLE IF NOT EXISTS conciliacao.analise_orcamento (
    id             bigserial PRIMARY KEY,
    id_orcamento   bigint NOT NULL,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    autor          text,
    provedor       text,
    modelo         text,
    payload_hash   text NOT NULL,
    payload        jsonb,
    resultado      jsonb NOT NULL,
    tokens_entrada integer,
    tokens_saida   integer
);
CREATE INDEX IF NOT EXISTS analise_orcamento_id ON conciliacao.analise_orcamento (id_orcamento, criado_em DESC);

-- v6: tipo de atendimento da admissão casada (0 hospital de transição, 1 home care, 3 ambulatorial)
ALTER TABLE conciliacao.cruzamento ADD COLUMN IF NOT EXISTS tipo_atendimento integer;

-- v7: leitos por unidade (não existem no ERP IW). tipo_atendimento: 0 hospital de transição.
CREATE TABLE IF NOT EXISTS conciliacao.parametro_leitos (
    unidade          text NOT NULL,
    tipo_atendimento integer NOT NULL DEFAULT 0,
    leitos           integer NOT NULL,
    vigente_desde    date NOT NULL
);

-- v8: motivos internos da pré-auditoria (CAPPAYMENTITEM.PREAUDITBILLREASON 1-4; os demais são TISS)
CREATE TABLE IF NOT EXISTS conciliacao.motivo_preauditoria (
    codigo    text PRIMARY KEY,
    descricao text NOT NULL
);

-- v9: id por linha nas premissas editáveis (Premissas › editar/excluir). A carga por CSV
-- continua substituindo a tabela inteira; os ids novos saem da sequência.
ALTER TABLE conciliacao.premissa_imposto ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.premissa_prazo ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.premissa_recurso ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.convenio_de_para ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.aging_faixa ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.empresa_convenio ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.parametro_leitos ADD COLUMN IF NOT EXISTS id bigserial;
ALTER TABLE conciliacao.motivo_preauditoria ADD COLUMN IF NOT EXISTS id bigserial;

-- v10: XML TISS de volta (DEMONSTRATIVO_ANALISE_CONTA), src/conciliacao/tiss_*.py.
-- Sobrepõe a planilha na glosa (valor e motivo); recurso, recuperado e perda seguem da planilha.
CREATE TABLE IF NOT EXISTS conciliacao.tiss_arquivo (
    id                   bigserial PRIMARY KEY,
    tipo                 text NOT NULL,
    sha256               text NOT NULL UNIQUE,
    arquivo              text NOT NULL,
    operadora_ans        text,
    operadora_nome       text,
    operadora_cnpj       text,
    numero_demonstrativo text,
    data_emissao         date,
    padrao               text,
    autor                text,
    recebido_em          timestamptz NOT NULL DEFAULT now(),
    informado            numeric,
    liberado             numeric,
    glosa                numeric,
    resumo               jsonb NOT NULL DEFAULT '{}'::jsonb,
    conteudo             bytea NOT NULL
);

CREATE TABLE IF NOT EXISTS conciliacao.tiss_guia (
    id               bigserial PRIMARY KEY,
    arquivo_id       bigint NOT NULL REFERENCES conciliacao.tiss_arquivo (id) ON DELETE CASCADE,
    protocolo        text NOT NULL,
    guia_prestador   text NOT NULL,
    guia_operadora   text,
    senha            text,
    carteira_hash    text,
    situacao_tiss    text,
    informado        numeric NOT NULL DEFAULT 0,
    processado       numeric NOT NULL DEFAULT 0,
    liberado         numeric NOT NULL DEFAULT 0,
    glosa            numeric NOT NULL DEFAULT 0,
    motivo_principal text,
    motivos          jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- casamento com o ERP (tiss_cruzamento.py)
    situacao         text,
    regra            text,
    id_conta         bigint,
    id_admissao      bigint,
    id_paciente      bigint,
    id_orcamento     bigint,
    tipo_atendimento integer,
    competencia      date,
    unidade_erp      text,
    operadora_erp    text,
    faturado_erp     numeric
);
CREATE INDEX IF NOT EXISTS tiss_guia_admissao ON conciliacao.tiss_guia (id_conta, id_admissao);
CREATE INDEX IF NOT EXISTS tiss_guia_arquivo ON conciliacao.tiss_guia (arquivo_id);

CREATE TABLE IF NOT EXISTS conciliacao.tiss_item (
    id               bigserial PRIMARY KEY,
    guia_id          bigint NOT NULL REFERENCES conciliacao.tiss_guia (id) ON DELETE CASCADE,
    sequencial       integer,
    data             date,
    tabela           text,
    codigo           text,
    descricao        text,
    quantidade       numeric,
    informado        numeric NOT NULL DEFAULT 0,
    processado       numeric NOT NULL DEFAULT 0,
    liberado         numeric NOT NULL DEFAULT 0,
    glosa            numeric NOT NULL DEFAULT 0,
    motivo_principal text,
    motivos          jsonb NOT NULL DEFAULT '[]'::jsonb,
    id_item_erp      bigint
);
CREATE INDEX IF NOT EXISTS tiss_item_guia ON conciliacao.tiss_item (guia_id);

-- Visões: recriadas a cada boot (DROP + CREATE), na ordem de dependência.
DROP VIEW IF EXISTS conciliacao.cruzamento_efetivo;
DROP VIEW IF EXISTS conciliacao.glosa_efetiva;
DROP VIEW IF EXISTS conciliacao.tiss_admissao;
DROP VIEW IF EXISTS conciliacao.tiss_guia_ativa;

-- A guia vale pelo demonstrativo mais recente do mesmo protocolo (reenvio da operadora substitui)
CREATE VIEW conciliacao.tiss_guia_ativa AS
SELECT DISTINCT ON (g.protocolo, g.guia_prestador) g.*, a.operadora_nome, a.data_emissao, a.numero_demonstrativo
  FROM conciliacao.tiss_guia g
  JOIN conciliacao.tiss_arquivo a ON a.id = g.arquivo_id
 ORDER BY g.protocolo, g.guia_prestador, a.data_emissao DESC NULLS LAST, a.id DESC;

-- Glosa do XML por admissão da conta (só guias casadas com o ERP)
CREATE VIEW conciliacao.tiss_admissao AS
SELECT t.*,
       (SELECT string_agg(DISTINCT mo->>'codigo', ', ' ORDER BY mo->>'codigo')
          FROM conciliacao.tiss_guia_ativa ga
          JOIN conciliacao.tiss_item it ON it.guia_id = ga.id AND it.glosa > 0
          CROSS JOIN LATERAL jsonb_array_elements(it.motivos) mo
         WHERE ga.id_conta = t.id_conta AND ga.id_admissao = t.id_admissao) AS motivos
  FROM (
    -- uma linha por admissão: somar ANTES de juntar os motivos (vários motivos por item)
    SELECT id_conta, id_admissao,
           MIN(id)                  AS guia_id,
           MAX(id_paciente)         AS id_paciente,
           MAX(tipo_atendimento)    AS tipo_atendimento,
           MAX(protocolo)           AS protocolo,
           MAX(competencia)         AS competencia,
           MAX(unidade_erp)         AS unidade_erp,
           MAX(operadora_erp)       AS operadora_erp,
           MAX(faturado_erp)        AS faturado_erp,
           SUM(informado)           AS informado,
           SUM(liberado)            AS liberado,
           SUM(glosa)               AS glosa,
           (ARRAY_AGG(motivo_principal ORDER BY glosa DESC) FILTER (WHERE motivo_principal IS NOT NULL))[1] AS motivo
      FROM conciliacao.tiss_guia_ativa
     WHERE id_admissao IS NOT NULL
     GROUP BY id_conta, id_admissao
  ) t;

-- Glosa efetiva: a linha da planilha com valor e motivo do XML quando a admissão tem retorno
-- (o total do XML fica na primeira linha da admissão), mais a glosa que só está no XML.
CREATE VIEW conciliacao.glosa_efetiva AS
WITH planilha AS (
    SELECT g.*, x.id_conta AS x_conta, x.id_admissao AS x_admissao,
           MIN(g.linha) OVER (PARTITION BY g.carga_id, x.id_conta, x.id_admissao) AS primeira_linha_adm
      FROM conciliacao.glosa_linha g
      LEFT JOIN conciliacao.cruzamento x ON x.carga_id = g.carga_id AND x.linha = g.linha
), xa AS (
    SELECT t.*, p.carga_id, p.primeira_linha
      FROM conciliacao.tiss_admissao t
      LEFT JOIN LATERAL (SELECT pl.carga_id, MIN(pl.linha) AS primeira_linha FROM planilha pl
                          WHERE pl.x_conta = t.id_conta AND pl.x_admissao = t.id_admissao
                          GROUP BY pl.carga_id) p ON true
)
SELECT g.carga_id,
       g.linha,
       g.empresa,
       g.filial,
       g.convenio,
       g.paciente,
       g.mod,
       g.periodo,
       g.protocolo,
       g.valor_faturado,
       g.data_entrega,
       g.data_prevista_recebimento,
       g.nota_fiscal,
       CASE WHEN xa.id_admissao IS NULL THEN g.glosa
            WHEN g.linha = xa.primeira_linha THEN xa.glosa ELSE 0 END AS glosa,
       g.valor_recebido,
       g.data_recebimento,
       g.obs_financeiro,
       g.devolucao,
       g.data_reapresentacao,
       g.protocolo_reapresentacao,
       CASE WHEN xa.id_admissao IS NULL THEN g.motivo ELSE xa.motivo END AS motivo,
       g.classificacao_bruta,
       g.valor_recursado,
       g.data_recurso,
       g.protocolo_recurso,
       g.previsao_pagto_recurso,
       g.glosa_acatada,
       g.data_receb_recurso,
       g.valor_recurso_bruto,
       g.valor_recurso_liquido,
       g.glosa_mantida,
       g.nf_recurso,
       g.observacao,
       g.banco,
       g.convenio_formula,
       g.convenio_formula_de_para,
       g.convenio_formula_manual,
       g.competencia,
       g.prazo,
       g.data_contratual,
       g.mes_previsao,
       g.imposto,
       g.valor_liquido,
       g.base_calculo_1,
       g.base_calculo_2,
       g.status,
       g.dias_atraso,
       g.aging,
       g.classificacao,
       g.status_glosa,
       g.prazo_recurso,
       g.pendencias,
       g.divergencias,
       g.planilha,
       g.paciente_codigo,
       CASE WHEN xa.id_admissao IS NULL THEN 'planilha' ELSE 'xml' END AS origem_glosa,
       xa.motivos AS motivos_xml,
       g.glosa AS glosa_planilha,
       g.motivo AS motivo_planilha
  FROM planilha g
  LEFT JOIN xa ON xa.id_conta = g.x_conta AND xa.id_admissao = g.x_admissao AND xa.carga_id = g.carga_id
UNION ALL
SELECT (SELECT id FROM conciliacao.carga WHERE ativa AND tipo = 'glosa') AS carga_id,
       -xs.guia_id AS linha,
       xs.unidade_erp AS empresa,
       'XML' AS filial,
       xs.operadora_erp AS convenio,
       NULL::text AS paciente,
       NULL::text AS mod,
       NULL::text AS periodo,
       xs.protocolo AS protocolo,
       xs.informado AS valor_faturado,
       NULL::date AS data_entrega,
       NULL::date AS data_prevista_recebimento,
       NULL::text AS nota_fiscal,
       xs.glosa AS glosa,
       NULL::numeric AS valor_recebido,
       NULL::date AS data_recebimento,
       NULL::text AS obs_financeiro,
       NULL::date AS devolucao,
       NULL::date AS data_reapresentacao,
       NULL::text AS protocolo_reapresentacao,
       xs.motivo AS motivo,
       NULL::text AS classificacao_bruta,
       NULL::numeric AS valor_recursado,
       NULL::date AS data_recurso,
       NULL::text AS protocolo_recurso,
       NULL::date AS previsao_pagto_recurso,
       NULL::numeric AS glosa_acatada,
       NULL::date AS data_receb_recurso,
       NULL::numeric AS valor_recurso_bruto,
       NULL::numeric AS valor_recurso_liquido,
       NULL::numeric AS glosa_mantida,
       NULL::text AS nf_recurso,
       NULL::text AS observacao,
       NULL::text AS banco,
       NULL::text AS convenio_formula,
       NULL::text AS convenio_formula_de_para,
       NULL::boolean AS convenio_formula_manual,
       xs.competencia AS competencia,
       NULL::integer AS prazo,
       NULL::date AS data_contratual,
       NULL::date AS mes_previsao,
       NULL::numeric AS imposto,
       NULL::numeric AS valor_liquido,
       NULL::numeric AS base_calculo_1,
       NULL::numeric AS base_calculo_2,
       NULL::text AS status,
       NULL::integer AS dias_atraso,
       NULL::text AS aging,
       'OPERADORA' AS classificacao,
       'ANÁLISE OPERADORA' AS status_glosa,
       NULL::date AS prazo_recurso,
       NULL::text[] AS pendencias,
       NULL::text[] AS divergencias,
       '{}'::jsonb AS planilha,
       'P' || xs.id_paciente::text AS paciente_codigo,
       'xml' AS origem_glosa,
       xs.motivos AS motivos_xml,
       NULL::numeric AS glosa_planilha,
       NULL::text AS motivo_planilha
  FROM xa xs
 WHERE xs.primeira_linha IS NULL AND xs.glosa > 0;

-- Cruzamento efetivo: o da planilha mais as linhas que só estão no XML
CREATE VIEW conciliacao.cruzamento_efetivo AS
SELECT carga_id, linha, situacao, id_conta, unidade_erp, operadora_erp, faturado_erp, glosa_iw, diferenca, principal,
       id_admissao, regra, protocolo_erp, id_paciente, tipo_atendimento
  FROM conciliacao.cruzamento
UNION ALL
SELECT (SELECT id FROM conciliacao.carga WHERE ativa AND tipo = 'glosa'), -t.guia_id, 'SÓ NO XML', t.id_conta,
       t.unidade_erp, t.operadora_erp, t.faturado_erp, 0, t.informado - t.faturado_erp, true, t.id_admissao, 'xml',
       t.protocolo, t.id_paciente, t.tipo_atendimento
  FROM conciliacao.tiss_admissao t
 WHERE t.glosa > 0 AND NOT EXISTS (SELECT 1 FROM conciliacao.cruzamento x
                                    JOIN conciliacao.carga c ON c.id = x.carga_id AND c.ativa AND c.tipo = 'glosa'
                                   WHERE x.id_conta = t.id_conta AND x.id_admissao = t.id_admissao);
