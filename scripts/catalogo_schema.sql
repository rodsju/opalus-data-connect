-- Schema do catalogo de dados, aplicado de forma idempotente por
-- scripts/mapear_oracle.py no inicio de cada execucao.
--
-- Nao mora em /docker-entrypoint-initdb.d de proposito: script de init do
-- Postgres so roda em volume vazio, entao a primeira mudanca de DDL exigiria
-- destruir o volume. Aqui o proprio mapeador reaplica.

CREATE SCHEMA IF NOT EXISTS catalogo;

-- pgp_sym_encrypt/decrypt para a chave dos provedores de IA
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tipo vector e o operador <=> (distancia de cosseno) dos embeddings. Exige a
-- imagem pgvector/pgvector:pg17 no compose -- a postgres:17-alpine nao traz a
-- extensao.
CREATE EXTENSION IF NOT EXISTS vector;

-- Configuracao geral do app: a escolha de QUAL cadastro usar quando ninguem
-- escolhe na hora. Hoje guarda o par provedor::modelo de embedding que a API de
-- descricoes usa -- ela nao tem tela com select, ao contrario da pagina do
-- objeto. Chave/valor em texto porque sao poucas chaves, todas escalares; um
-- jsonb unico transformaria cada leitura num parse.
CREATE TABLE IF NOT EXISTS catalogo.configuracao (
  chave          text PRIMARY KEY,
  valor          text NOT NULL,
  atualizado_em  timestamptz NOT NULL DEFAULT now(),
  atualizado_por text
);

-- Provedores de IA cadastrados em Setup > AI Providers. A chave fica cifrada com
-- a senha mestra de IA_SENHA_MESTRA (.env): um dump do Postgres sozinho nao a
-- revela. Nao ha FK de descricao_ia.provedor para ca DE PROPOSITO -- apagar um
-- provedor nao pode apagar o historico de descricoes que ele gerou.
CREATE TABLE IF NOT EXISTS catalogo.provedor_ia (
  id            bigserial PRIMARY KEY,
  slug          text NOT NULL UNIQUE,   -- identidade; e o que descricao_ia grava
  nome          text NOT NULL,
  tipo          text NOT NULL CHECK (tipo IN ('anthropic', 'openai')),
  -- Protocolo (tipo) e oficio (capacidade) sao coisas diferentes: o mesmo
  -- endpoint openai serve chat e embeddings, mas um modelo nao faz os dois. Sem
  -- isto um modelo de embedding apareceria no select de gerar descricao.
  capacidade    text NOT NULL DEFAULT 'llm' CHECK (capacidade IN ('llm', 'embedding')),
  url           text NOT NULL DEFAULT '',
  modelos       text[] NOT NULL,
  chave_cifrada bytea NOT NULL,
  chave_final   text NOT NULL,          -- ultimos 4 caracteres, so para exibir
  ativo         boolean NOT NULL DEFAULT true,
  criado_em     timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);

-- Linha unica com o estado da ultima extracao. O CHECK trava o id em 1: nao
-- guardamos historico, o catalogo e sempre a foto corrente do schema.
CREATE TABLE IF NOT EXISTS catalogo.extracao (
  id                   int PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  schema_origem        text NOT NULL,
  host                 text NOT NULL,
  service_name         text NOT NULL,
  iniciada_em          timestamptz NOT NULL,
  concluida_em         timestamptz,
  status               text NOT NULL,          -- em_andamento | concluida | falhou
  parametros           jsonb NOT NULL DEFAULT '{}'::jsonb,
  erros                jsonb NOT NULL DEFAULT '[]'::jsonb
);

-- ---------------------------------------------------------------------------
-- Servidor e esquema: de onde o objeto veio
--
-- Ate aqui o catalogo tinha um servidor e um schema IMPLICITOS -- existiam so
-- como texto em catalogo.extracao, e nenhuma tabela sabia a origem do dado. Estas
-- duas tabelas dao a hierarquia servidor -> esquema -> objeto, para o dia em que
-- houver o segundo. Hoje ha um de cada.
--
-- A CREDENCIAL NAO MORA AQUI: continua no .env, lida pelo mapeador. Guardar
-- segredo no catalogo tem o padrao cifrado de provedor_ia (pgp_sym_encrypt com a
-- IA_SENHA_MESTRA) pronto para copiar quando fizer sentido -- e note que o
-- mapeador hoje nem conhece essa senha.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS catalogo.servidor (
  id        bigserial PRIMARY KEY,
  tipo      text NOT NULL CHECK (tipo IN ('oracle', 'mssql', 'postgres', 'mysql')),
  host      text NOT NULL,
  porta     int  NOT NULL,
  -- service name no Oracle, database no Postgres/MSSQL. Um nome so porque o papel
  -- e o mesmo: o que vai depois do host no DSN.
  base      text NOT NULL,
  nome      text NOT NULL,                    -- rotulo de tela
  ativo     boolean NOT NULL DEFAULT true,
  criado_em timestamptz NOT NULL DEFAULT now(),
  -- Chave natural, sem slug: o que identifica um servidor e para onde ele aponta.
  UNIQUE (tipo, host, porta, base)
);

CREATE TABLE IF NOT EXISTS catalogo.esquema (
  id          bigserial PRIMARY KEY,
  servidor_id bigint NOT NULL REFERENCES catalogo.servidor(id) ON DELETE CASCADE,
  nome        text NOT NULL,
  criado_em   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (servidor_id, nome)
);

CREATE TABLE IF NOT EXISTS catalogo.objeto (
  id                   bigserial PRIMARY KEY,
  -- NOT NULL aqui e anulavel no ALTER la embaixo, e a divergencia e proposital:
  -- banco novo nasce com a coluna obrigatoria, banco de pe precisa da janela
  -- entre acrescentar a coluna e preencher o backfill. Ver o bloco "Servidor e
  -- esquema" no fim do arquivo.
  esquema_id           bigint NOT NULL REFERENCES catalogo.esquema(id) ON DELETE CASCADE,
  nome                 text NOT NULL,
  tipo                 text NOT NULL,          -- TABLE | VIEW
  comentario           text,
  num_registros        bigint,                 -- null = estatistica nunca coletada
  contagem_aproximada  boolean NOT NULL DEFAULT true,
  contagem_coletada_em timestamptz,
  tem_registros        boolean,                -- vem da amostra, nao da estatistica
  particionada         boolean,
  view_sql             text,
  atualizado_em        timestamptz NOT NULL DEFAULT now(),
  erros                jsonb NOT NULL DEFAULT '[]'::jsonb,
  -- Vetor da descricao da tabela (rotulo + resumo + funcao). Ver o bloco de
  -- embeddings mais abaixo para o porque de vector sem dimensao.
  embedding            vector,
  embedding_modelo     text,
  embedding_dim        int,
  embedding_hash       text,
  embedding_em         timestamptz,
  -- Era UNIQUE (nome) -- o nome so podia ser unico enquanto houvesse um schema.
  UNIQUE (esquema_id, nome)
);

CREATE TABLE IF NOT EXISTS catalogo.coluna (
  id            bigserial PRIMARY KEY,
  objeto_id     bigint NOT NULL REFERENCES catalogo.objeto(id) ON DELETE CASCADE,
  posicao       int NOT NULL,
  nome          text NOT NULL,
  tipo          text NOT NULL,                 -- NUMBER, VARCHAR2, DATE...
  tipo_completo text NOT NULL,                 -- NUMBER(10,2), VARCHAR2(60 CHAR)
  tamanho       int,
  precisao      int,
  escala        int,
  aceita_nulo   boolean NOT NULL,
  valor_default text,
  comentario    text,
  eh_pk         boolean NOT NULL DEFAULT false,
  na_amostra    boolean NOT NULL DEFAULT true, -- false = tipo pulado no SELECT da amostra
  -- Descricao do campo materializada do jsonb descricao_ia.campos: o vetor
  -- precisa de um texto por linha. Escrita pelo app, nunca pelo mapeador --
  -- por isso gravar_objeto() faz upsert em vez de apagar e reinserir.
  descricao_ia     text,
  embedding        vector,
  embedding_modelo text,
  embedding_dim    int,
  embedding_hash   text,
  embedding_em     timestamptz,
  -- Veredito da IA sobre o campo carregar dado sensivel. Escrito direto aqui, e
  -- nao projetado de um jsonb por objeto como descricao_ia: a unidade do
  -- julgamento e a coluna. NULL = nao avaliada, que NAO e o mesmo que "nao e
  -- sensivel" -- foi confundir as duas coisas que fez a antiga amostra.mascarada
  -- dar uma garantia falsa.
  sensivel           boolean,
  sensivel_categoria text,      -- nome|documento|contato|endereco|clinico|credencial|financeiro|nenhuma
  sensivel_motivo    text,
  sensivel_modelo    text,
  sensivel_em        timestamptz,
  -- Observado na AMOSTRA, nao na tabela: a amostra sao as 100 linhas mais
  -- recentes, entao coluna abandonada ha anos aparece como sempre nula mesmo
  -- tendo historico. Tres estados como sensivel -- NULL e "nao avaliada", que
  -- nao e "tem valor": fica nulo quando o objeto nao tem amostra ou quando a
  -- coluna nem entra no SELECT dela (na_amostra = false).
  sempre_nulo        boolean,
  sempre_nulo_em     timestamptz,
  UNIQUE (objeto_id, nome)
);

CREATE TABLE IF NOT EXISTS catalogo.restricao (
  id           bigserial PRIMARY KEY,
  objeto_id    bigint NOT NULL REFERENCES catalogo.objeto(id) ON DELETE CASCADE,
  nome         text NOT NULL,
  tipo         text NOT NULL,                  -- P | U | R
  colunas      text[] NOT NULL,
  ref_schema   text,
  ref_tabela   text,
  ref_colunas  text[],
  delete_rule  text,
  status       text,
  UNIQUE (objeto_id, nome)
);

CREATE TABLE IF NOT EXISTS catalogo.indice (
  id        bigserial PRIMARY KEY,
  objeto_id bigint NOT NULL REFERENCES catalogo.objeto(id) ON DELETE CASCADE,
  nome      text NOT NULL,
  unico     boolean NOT NULL,
  tipo      text,
  colunas   text[] NOT NULL,
  UNIQUE (objeto_id, nome)
);

-- Aresta do grafo, desnormalizada de proposito: e a tabela que se consulta para
-- responder "quem depende de X", sem join nenhum.
CREATE TABLE IF NOT EXISTS catalogo.relacionamento (
  id              bigserial PRIMARY KEY,
  -- Do esquema da ORIGEM. O destino continua texto (destino_schema) porque em
  -- base legada a FK aponta para fora do schema mapeado, e esse destino pode nem
  -- existir em catalogo.objeto -- por isso aqui nao ha FK por id.
  esquema_id      bigint NOT NULL REFERENCES catalogo.esquema(id) ON DELETE CASCADE,
  constraint_nome text NOT NULL,
  origem_tabela   text NOT NULL,
  origem_colunas  text[] NOT NULL,
  destino_schema  text NOT NULL,
  destino_tabela  text NOT NULL,
  destino_colunas text[] NOT NULL,
  delete_rule     text,
  UNIQUE (esquema_id, origem_tabela, constraint_nome)
);

-- Relacionamento que o banco NAO declara -- inferido por nome de coluna, tipo,
-- cardinalidade ou IA. Replica de relacionamento, mais a procedencia: sugestao
-- sem metodo e sem confianca e ruido, porque ninguem revisa o que nao sabe de
-- onde veio. Sem coluna de status de propósito -- aceitar/rejeitar e fluxo de
-- revisao, e ainda nao existe nada que preencha nem consuma esta tabela.
CREATE TABLE IF NOT EXISTS catalogo.relacionamento_sugerido (
  id              bigserial PRIMARY KEY,
  esquema_id      bigint NOT NULL REFERENCES catalogo.esquema(id) ON DELETE CASCADE,
  origem_tabela   text NOT NULL,
  origem_colunas  text[] NOT NULL,
  destino_schema  text NOT NULL,
  destino_tabela  text NOT NULL,
  destino_colunas text[] NOT NULL,
  metodo          text NOT NULL,           -- como a sugestao apareceu
  confianca       real,                    -- 0..1
  motivo          text,
  criado_em       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (esquema_id, origem_tabela, origem_colunas, destino_tabela, destino_colunas)
);

CREATE TABLE IF NOT EXISTS catalogo.amostra (
  id        bigserial PRIMARY KEY,
  objeto_id bigint NOT NULL REFERENCES catalogo.objeto(id) ON DELETE CASCADE,
  linha     int NOT NULL,
  mascarada boolean NOT NULL,
  dados     jsonb NOT NULL,
  UNIQUE (objeto_id, linha)
);

-- Descricao gerada por IA a partir da estrutura + amostra do objeto. Quem escreve e
-- o app (src/ia.py), nao o mapeador -- por isso NAO entre na lista de filhas apagadas
-- e reinseridas por gravar_objeto(): o upsert do objeto preserva o id, entao a
-- descricao sobrevive a uma nova extracao.
CREATE TABLE IF NOT EXISTS catalogo.descricao_ia (
  id                bigserial PRIMARY KEY,
  objeto_id         bigint NOT NULL UNIQUE REFERENCES catalogo.objeto(id) ON DELETE CASCADE,
  rotulo            text NOT NULL DEFAULT '', -- ate 5 palavras, para listagem
  resumo            text NOT NULL,          -- o que a tabela guarda
  funcao            text NOT NULL DEFAULT '', -- que papel ela cumpre no sistema
  dominio           text,
  -- [{tabela, motivo}] -- a lista de tabelas vem das FKs reais; a IA da o motivo
  dependencias      jsonb NOT NULL DEFAULT '[]'::jsonb,  -- de quem esta depende
  dependentes       jsonb NOT NULL DEFAULT '[]'::jsonb,  -- quem depende desta
  campos            jsonb NOT NULL DEFAULT '[]'::jsonb,  -- [{coluna, descricao}]
  provedor          text NOT NULL,
  modelo            text NOT NULL,
  gerado_em         timestamptz NOT NULL DEFAULT now(),
  colunas_descritas int NOT NULL,
  linhas_no_prompt  int NOT NULL,   -- quantas linhas da amostra couberam no orcamento
  tokens_entrada    int,
  tokens_saida      int,
  -- Edicao vinda da API JSON (src/api.py). Nao sobrescreve provedor/modelo.
  editado_por       text,
  editado_em        timestamptz
);

-- Lote de descricoes disparado por Setup > Lote de descricoes. O script
-- scripts/descrever_lote.py roda destacado do app e vai marcando cada item; e o
-- item por tabela que torna o lote retomavel depois de um reinicio.
CREATE TABLE IF NOT EXISTS catalogo.lote_ia (
  id           bigserial PRIMARY KEY,
  tarefa       text NOT NULL DEFAULT 'descricao'    -- descricao | embedding | mascara
                    CHECK (tarefa IN ('descricao', 'embedding', 'mascara')),
  provedor     text NOT NULL,
  modelo       text NOT NULL,
  paralelismo  int  NOT NULL DEFAULT 4,
  filtro       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- o recorte que a tela usou
  status       text NOT NULL DEFAULT 'pendente',    -- pendente|rodando|concluido|cancelado
  criado_por   text,
  criado_em    timestamptz NOT NULL DEFAULT now(),
  iniciado_em  timestamptz,
  terminado_em timestamptz
);

CREATE TABLE IF NOT EXISTS catalogo.lote_ia_item (
  id             bigserial PRIMARY KEY,
  lote_id        bigint NOT NULL REFERENCES catalogo.lote_ia(id) ON DELETE CASCADE,
  objeto_id      bigint NOT NULL REFERENCES catalogo.objeto(id) ON DELETE CASCADE,
  status         text NOT NULL DEFAULT 'pendente',  -- pendente|rodando|concluido|falhou
  erro           text,
  tokens_entrada int,
  tokens_saida   int,
  iniciado_em    timestamptz,
  terminado_em   timestamptz,
  UNIQUE (lote_id, objeto_id)
);

CREATE INDEX IF NOT EXISTS lote_ia_item_pendente_idx
    ON catalogo.lote_ia_item (lote_id) WHERE status = 'pendente';

CREATE INDEX IF NOT EXISTS amostra_dados_idx ON catalogo.amostra USING gin (dados);
CREATE INDEX IF NOT EXISTS relacionamento_destino_idx ON catalogo.relacionamento (destino_tabela);
CREATE INDEX IF NOT EXISTS coluna_nome_idx ON catalogo.coluna (nome);


-- ---------------------------------------------------------------------------
-- Colunas acrescentadas depois -- por que os ALTER existem
--
-- CREATE TABLE IF NOT EXISTS e no-op em tabela que ja existe: sozinho ele so
-- alcanca banco novo. Como este schema se reaplica sobre um banco populado,
-- toda coluna nova precisa das duas metades -- o corpo do CREATE TABLE la em
-- cima, para o banco novo, e um ALTER aqui, para o que ja esta de pe. Os dois
-- tem de dizer a mesma coisa; divergiram, o banco novo e o antigo passam a ter
-- schemas diferentes.
-- ---------------------------------------------------------------------------

ALTER TABLE catalogo.provedor_ia
  ADD COLUMN IF NOT EXISTS capacidade text NOT NULL DEFAULT 'llm';
DO $$ BEGIN
  ALTER TABLE catalogo.provedor_ia
    ADD CONSTRAINT provedor_ia_capacidade_check CHECK (capacidade IN ('llm', 'embedding'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE catalogo.objeto
  ADD COLUMN IF NOT EXISTS embedding        vector,
  ADD COLUMN IF NOT EXISTS embedding_modelo text,
  ADD COLUMN IF NOT EXISTS embedding_dim    int,
  ADD COLUMN IF NOT EXISTS embedding_hash   text,
  ADD COLUMN IF NOT EXISTS embedding_em     timestamptz;

ALTER TABLE catalogo.coluna
  ADD COLUMN IF NOT EXISTS descricao_ia     text,
  ADD COLUMN IF NOT EXISTS embedding        vector,
  ADD COLUMN IF NOT EXISTS embedding_modelo text,
  ADD COLUMN IF NOT EXISTS embedding_dim    int,
  ADD COLUMN IF NOT EXISTS embedding_hash   text,
  ADD COLUMN IF NOT EXISTS embedding_em     timestamptz,
  ADD COLUMN IF NOT EXISTS sensivel           boolean,
  ADD COLUMN IF NOT EXISTS sensivel_categoria text,
  ADD COLUMN IF NOT EXISTS sensivel_motivo    text,
  ADD COLUMN IF NOT EXISTS sensivel_modelo    text,
  ADD COLUMN IF NOT EXISTS sensivel_em        timestamptz,
  ADD COLUMN IF NOT EXISTS sempre_nulo        boolean,
  ADD COLUMN IF NOT EXISTS sempre_nulo_em     timestamptz;

-- Quem editou a descricao por fora da IA (API JSON). Colunas proprias, e nao
-- sobrescrever provedor/modelo: aqueles dizem quem GEROU o texto, e apagar isso
-- numa edicao manual perderia a unica pista de como a descricao nasceu.
ALTER TABLE catalogo.descricao_ia
  ADD COLUMN IF NOT EXISTS editado_por text,
  ADD COLUMN IF NOT EXISTS editado_em  timestamptz;

ALTER TABLE catalogo.lote_ia
  ADD COLUMN IF NOT EXISTS tarefa text NOT NULL DEFAULT 'descricao';
-- DROP + ADD, e nao o DO $$ ... EXCEPTION duplicate_object que estava aqui: num
-- banco onde a constraint ja existe o ADD levanta duplicate_object e o bloco
-- engole a excecao, entao acrescentar um valor ao CHECK nao teria efeito nenhum
-- -- o banco continuaria recusando 'mascara' enquanto o arquivo dizia aceitar.
ALTER TABLE catalogo.lote_ia DROP CONSTRAINT IF EXISTS lote_ia_tarefa_check;
ALTER TABLE catalogo.lote_ia
  ADD CONSTRAINT lote_ia_tarefa_check
      CHECK (tarefa IN ('descricao', 'embedding', 'mascara'));


-- ---------------------------------------------------------------------------
-- Servidor e esquema: acrescentar e preencher num banco ja populado
--
-- Esta e a unica coluna do arquivo em que as duas metades divergem: no CREATE
-- TABLE ela e NOT NULL, aqui ela nasce anulavel. Nao ha como fazer diferente --
-- num banco com 2.269 objetos a coluna tem de existir antes de poder ser
-- preenchida. Os quatro passos abaixo fecham a janela na mesma execucao.
--
-- O backfill nao precisa de Python: catalogo.extracao ja guarda schema_origem,
-- host e service_name do que foi mapeado, entao o proprio DDL sabe de onde o
-- catalogo veio. Banco novo nao tem essa linha -- la quem cria o esquema e o
-- garantir_esquema() do mapeador, com os dados do .env.
-- ---------------------------------------------------------------------------

-- 1. O servidor e o esquema do que ja esta mapeado
INSERT INTO catalogo.servidor (tipo, host, porta, base, nome)
SELECT 'oracle', e.host, 1521, e.service_name, e.host || '/' || e.service_name
  FROM catalogo.extracao e
 WHERE e.id = 1
ON CONFLICT (tipo, host, porta, base) DO NOTHING;

INSERT INTO catalogo.esquema (servidor_id, nome)
SELECT s.id, e.schema_origem
  FROM catalogo.extracao e
  JOIN catalogo.servidor s
    ON s.tipo = 'oracle' AND s.host = e.host AND s.base = e.service_name
 WHERE e.id = 1
ON CONFLICT (servidor_id, nome) DO NOTHING;

-- 2. As colunas, anulaveis
ALTER TABLE catalogo.objeto
  ADD COLUMN IF NOT EXISTS esquema_id bigint REFERENCES catalogo.esquema(id) ON DELETE CASCADE;
ALTER TABLE catalogo.relacionamento
  ADD COLUMN IF NOT EXISTS esquema_id bigint REFERENCES catalogo.esquema(id) ON DELETE CASCADE;

-- 3. Backfill. So faz sentido com UM esquema -- que e exatamente a situacao de
--    quem esta migrando. Com dois ja gravados, nao ha o que adivinhar, e o
--    UPDATE nao encosta em nada.
UPDATE catalogo.objeto SET esquema_id = (SELECT id FROM catalogo.esquema)
 WHERE esquema_id IS NULL AND (SELECT count(*) FROM catalogo.esquema) = 1;
UPDATE catalogo.relacionamento SET esquema_id = (SELECT id FROM catalogo.esquema)
 WHERE esquema_id IS NULL AND (SELECT count(*) FROM catalogo.esquema) = 1;

-- 4. As constraints. DROP + ADD, e nao o DO $$ ... EXCEPTION duplicate_object:
--    aquele engole a mudanca em silencio num banco onde a constraint ja existe.
--    NULLS NOT DISTINCT importa enquanto houver linha com esquema_id nulo -- sem
--    ele, o nulo escaparia da unicidade sem avisar.
ALTER TABLE catalogo.objeto DROP CONSTRAINT IF EXISTS objeto_nome_key;
ALTER TABLE catalogo.objeto DROP CONSTRAINT IF EXISTS objeto_esquema_id_nome_key;
ALTER TABLE catalogo.objeto
  ADD CONSTRAINT objeto_esquema_id_nome_key UNIQUE NULLS NOT DISTINCT (esquema_id, nome);

ALTER TABLE catalogo.relacionamento
  DROP CONSTRAINT IF EXISTS relacionamento_origem_tabela_constraint_nome_key;
ALTER TABLE catalogo.relacionamento
  DROP CONSTRAINT IF EXISTS relacionamento_esquema_id_origem_tabela_constraint_nome_key;
ALTER TABLE catalogo.relacionamento
  ADD CONSTRAINT relacionamento_esquema_id_origem_tabela_constraint_nome_key
      UNIQUE NULLS NOT DISTINCT (esquema_id, origem_tabela, constraint_nome);

-- 5. NOT NULL assim que nao houver orfao. Banco novo (sem linhas) trava ja; o
--    populado trava nesta mesma passada, logo depois do backfill do passo 3.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM catalogo.objeto WHERE esquema_id IS NULL) THEN
    ALTER TABLE catalogo.objeto ALTER COLUMN esquema_id SET NOT NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM catalogo.relacionamento WHERE esquema_id IS NULL) THEN
    ALTER TABLE catalogo.relacionamento ALTER COLUMN esquema_id SET NOT NULL;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS objeto_esquema_idx ON catalogo.objeto (esquema_id);
CREATE INDEX IF NOT EXISTS relacionamento_esquema_idx ON catalogo.relacionamento (esquema_id);


-- ---------------------------------------------------------------------------
-- Embeddings: por que vector sem dimensao, e o que isso custa
--
-- O modelo de embedding e escolhido na tela, e cada um tem a sua dimensao
-- (1536, 768, 4096...). Fixar vector(N) aqui obrigaria a mexer no schema a cada
-- troca de modelo, entao a coluna fica sem dimensao declarada. O preco vem em
-- dois pedacos:
--
-- 1) pgvector so indexa (ivfflat/hnsw) coluna de dimensao fixa. Sem indice a
--    busca e sequencial -- ~53 mil colunas, aceitavel para uso interno. Fechado
--    o modelo, o caminho e ALTER COLUMN embedding TYPE vector(N) e criar o
--    indice HNSW com vector_cosine_ops.
--
-- 2) o operador <=> recusa vetores de dimensoes diferentes. Como a coluna pode
--    guardar vetores de modelos distintos, TODA consulta de similaridade tem de
--    filtrar por embedding_modelo -- e para isso que servem os indices abaixo.
--    Sem esse filtro a consulta nao devolve resultado ruim: ela levanta erro.
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS objeto_embedding_modelo_idx ON catalogo.objeto (embedding_modelo);
CREATE INDEX IF NOT EXISTS coluna_embedding_modelo_idx ON catalogo.coluna (embedding_modelo);


-- ---------------------------------------------------------------------------
-- Views: e o que faz o catalogo ser util sem conhecer o modelo de cor
-- ---------------------------------------------------------------------------

-- O dicionario de dados legivel de ponta a ponta.
CREATE OR REPLACE VIEW catalogo.vw_dicionario AS
SELECT o.nome          AS objeto,
       o.tipo          AS objeto_tipo,
       o.num_registros,
       c.posicao,
       c.nome          AS coluna,
       c.tipo_completo,
       c.aceita_nulo,
       c.eh_pk,
       c.valor_default,
       c.comentario,
       c.na_amostra,
       ia.descricao AS descricao_ia,
       -- No FIM da lista de proposito: CREATE OR REPLACE VIEW so acrescenta
       -- coluna no fim -- inserir no meio faz o Postgres recusar com "cannot
       -- change name of view column", e o schema deixaria de reaplicar.
       c.sensivel,
       c.sensivel_categoria,
       c.sempre_nulo
  FROM catalogo.objeto o
  JOIN catalogo.coluna c ON c.objeto_id = o.id
  -- A descricao gerada por IA e por coluna, guardada como jsonb em descricao_ia.
  -- LEFT + LATERAL: objeto sem descricao continua aparecendo, e a busca dentro do
  -- array e por objeto, nao um cross join com as 52.975 colunas.
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id
  LEFT JOIN LATERAL (
    SELECT campo->>'descricao' AS descricao
      FROM jsonb_array_elements(d.campos) campo
     WHERE campo->>'coluna' = c.nome
     LIMIT 1
  ) ia ON true;

-- Arestas em texto plano: ATENDIMENTO.CD_PACIENTE -> PACIENTE.CD_PACIENTE
CREATE OR REPLACE VIEW catalogo.vw_relacionamentos AS
SELECT r.origem_tabela || '.' || array_to_string(r.origem_colunas, ',')   AS origem,
       r.destino_tabela || '.' || array_to_string(r.destino_colunas, ',') AS destino,
       r.origem_tabela,
       r.origem_colunas,
       r.destino_schema,
       r.destino_tabela,
       r.destino_colunas,
       r.constraint_nome,
       r.delete_rule
  FROM catalogo.relacionamento r;

-- Uma linha por objeto: o panorama para decidir por onde comecar a olhar.
CREATE OR REPLACE VIEW catalogo.vw_resumo AS
SELECT o.nome,
       o.tipo,
       o.num_registros,
       o.contagem_aproximada,
       o.tem_registros,
       (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = o.id)         AS n_colunas,
       EXISTS (SELECT 1 FROM catalogo.restricao r
                WHERE r.objeto_id = o.id AND r.tipo = 'P')                       AS tem_pk,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.origem_tabela = o.nome)                                         AS fks_saindo,
       (SELECT count(*) FROM catalogo.relacionamento r
         WHERE r.destino_tabela = o.nome)                                        AS fks_entrando,
       (SELECT count(*) FROM catalogo.amostra a WHERE a.objeto_id = o.id)        AS linhas_amostra,
       jsonb_array_length(o.erros)                                               AS n_erros,
       coalesce(d.rotulo, '')                                                    AS rotulo
  FROM catalogo.objeto o
  -- Legenda de ate 5 palavras gerada por IA; LEFT porque a maioria ainda nao tem
  LEFT JOIN catalogo.descricao_ia d ON d.objeto_id = o.id;

-- Tabelas sem FK entrando nem saindo. Em base legada isso quase sempre
-- significa relacionamento nao declarado: e a proxima lista de investigacao.
CREATE OR REPLACE VIEW catalogo.vw_orfas AS
SELECT o.nome,
       o.tipo,
       o.num_registros,
       (SELECT count(*) FROM catalogo.coluna c WHERE c.objeto_id = o.id) AS n_colunas
  FROM catalogo.objeto o
 WHERE o.tipo = 'TABLE'
   AND NOT EXISTS (SELECT 1 FROM catalogo.relacionamento r WHERE r.origem_tabela = o.nome)
   AND NOT EXISTS (SELECT 1 FROM catalogo.relacionamento r WHERE r.destino_tabela = o.nome);
