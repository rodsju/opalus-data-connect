# Tabelas Oracle utilizadas — Reports, Consultas e Conciliação

Inventário das tabelas do ERP (Oracle) que o app **lê de fato** nos módulos
`src/reports`, `src/consultas` e `src/conciliacao`. Fica de fora tudo que só aparece no
mapeamento completo do schema (`scripts/mapear_oracle.py` / catálogo `/oracle`).

> **Atualização (13/11/2026):** o app não lê mais o Oracle. Todas as consultas foram
> portadas para `src/reports/sql_bq.py` e rodam na camada bronze do BigQuery
> (`fonte_bq.py`); `sql_oracle.py` e `fonte_oracle.py` saíram (estão no histórico do
> git). As tabelas abaixo são as mesmas, replicadas na bronze. Dos formulários TD*,
> só 12 estão na bronze hoje.

As tabelas do schema `conciliacao.*` e `catalogo.*` são Postgres (do próprio app),
não Oracle, e não estão aqui.

Levantado em **04/11/2026**.

## Como os tamanhos foram estimados

- **Linhas**: `ALL_TABLES.NUM_ROWS` (estatística do otimizador). A data da coleta está na
  coluna *Estatística*; tabelas analisadas em 05/03/2026 podem estar defasadas.
- **Dados (GB)**: `ALL_TABLES.BLOCKS × 8 KB`, ou seja, o espaço alocado abaixo da high-water
  mark. Bate com `NUM_ROWS × AVG_ROW_LEN` (ex.: `CAPPAYMENTITEMWORK` dá 4,36 GB por
  blocos e 3,95 GB por linha média), o que confirma o bloco de 8 KB.
- **Índices (GB)**: soma de `ALL_INDEXES.LEAF_BLOCKS × 8 KB` dos índices da tabela.
- **Limitações**: o usuário da aplicação não é dono do schema e não enxerga `DBA_SEGMENTS`
  nem `V$PARAMETER`, então os números são **estimativas** e não o tamanho físico exato.
  **LOBs fora da linha não entram na conta.** As tabelas com colunas CLOB estão marcadas
  com †, e o tamanho real delas pode ser maior.
- GB em base decimal (10⁹ bytes). "< 0,01" significa menos de 10 MB.

## Resumo

| Grupo | Tabelas | Dados (GB) | Índices (GB) | Total (GB) |
|---|---:|---:|---:|---:|
| Faturamento, orçamento e auditoria | 7 | 5,81 | 2,71 | 8,51 |
| Assistencial: evolução, agenda, prescrição | 8 | 1,15 | 1,31 | 2,47 |
| Materiais e medicamentos | 3 | 3,35 | 6,99 | 10,34 |
| Cadastros e domínios | 9 | 0,10 | 0,15 | 0,24 |
| **Subtotal das tabelas fixas** | **27** | **10,41** | **11,16** | **21,56** |
| Formulários de evolução TD* (dinâmicas, ver seção 5) | 71 | 16,49 | 0,19 | 16,68 |

As maiores tabelas são `MATMATERIALMOV` (~10 GB com índices), `CAPPAYMENTITEMWORK` (~6 GB) e
os formulários `TDWD_VISITAS_HC` (~7,4 GB) e `TDWD_VISITAS_HSP` (~3,5 GB, mais os CLOBs).

Dos 16,7 GB de formulários TD*, só ~11,4 GB são necessários hoje (3 essenciais + 11
recomendadas). `TDWD_VISITAS_HC3` (~5,2 GB) não tem evoluções há 12 meses e pode ficar de
fora. Ver a seção 5.

Legenda da coluna **Uso**: **R** = reports, **C** = consultas, **Z** = conciliação.

## 1. Faturamento, orçamento e auditoria

| Tabela | Linhas | Colunas | Dados (GB) | Índices (GB) | Total (GB) | Estatística | Uso | Para quê |
|---|---:|---:|---:|---:|---:|---|---|---|
| `CAPPAYMENT` | 69.912 | 55 | 0,01 | < 0,01 | 0,02 | 2026-09-08 | R C Z | Conta / fatura: status, protocolo, NF, competência |
| `CAPPAYMENTITEM` | 5.469.209 | 81 | 0,82 | 0,55 | 1,37 | 2026-10-08 | R C Z | Itens da conta: cobrado, glosa, pré-auditoria, recurso |
| `CAPPAYMENTITEMWORK` | 37.954.759 | 43 | 4,36 | 1,73 | 6,09 | 2026-09-10 | Z | Versão de trabalho dos itens, usada só no cruzamento de protocolos (`conciliacao/cruzamento`) |
| `CAPBUDGET` | 182.644 | 54 | 0,03 | < 0,01 | 0,04 | 2026-09-29 | R C Z | Orçamento / guia: status, senha TISS |
| `CAPBUDGETITEM` | 4.354.599 | 37 | 0,39 | 0,36 | 0,76 | 2026-09-18 | R C | Itens do orçamento (gap orçado × faturado) |
| `CAPADMISSION` † | 32.186 | 194 | 0,02 | 0,01 | 0,03 | 2026-09-30 | R C Z | Admissão / atendimento: tipo, unidade, entrada e saída, desfecho |
| `TTMPAUDITBILLCTR` | 1.917.972 | 22 | 0,18 | 0,04 | 0,21 | 2026-10-16 | R | Última execução da auditoria por unidade (`bloco_auditoria`) |

## 2. Assistencial: evolução, agenda e prescrição

Todas são usadas pela consulta de evolução (`consultas/evolucao`).

| Tabela | Linhas | Colunas | Dados (GB) | Índices (GB) | Total (GB) | Estatística | Uso | Para quê |
|---|---:|---:|---:|---:|---:|---|---|---|
| `CAPEVOLUTION` | 2.003.963 | 35 | 0,47 | 0,33 | 0,80 | 2026-09-23 | C | Evoluções; `IDTEMPLATE` aponta o formulário TD* |
| `CAPCONSULT` | 3.540.402 | 99 | 0,63 | 0,96 | 1,59 | 2026-09-22 | C | Agenda do ambulatório: sessões, comparecimento |
| `CAPPRESCRIPTION` | 134.741 | 70 | 0,02 | 0,02 | 0,05 | 2026-10-06 | C | Prescrições ligadas à evolução |
| `CAPINTERCURRENT` † | 26.231 | 31 | 0,04 | < 0,01 | 0,04 | 2026-09-12 | C | Intercorrências |
| `CAPINTERCURRENTCFG` | 9 | 11 | < 0,01 | < 0,01 | < 0,01 | 2026-03-05 | C | Tipos de intercorrência |
| `CAPINTERCLASSIF` | 83 | 5 | < 0,01 | < 0,01 | < 0,01 | 2026-03-05 | C | Classificação de intercorrência |
| `GLBTEMPLATE` | 217 | 15 | < 0,01 | < 0,01 | < 0,01 | 2026-09-30 | C | Formulário → `TABLENAME` (qual TD* ler) |
| `GLBTEMPLATEVAR` | 4.040 | 33 | < 0,01 | < 0,01 | < 0,01 | 2026-09-01 | C | Rótulo e domínio de cada campo dos formulários |

## 3. Materiais e medicamentos

Usadas pelos blocos `bloco_med_*` (`reports/med_comum`, `reports/bloco_med_estoque`).

| Tabela | Linhas | Colunas | Dados (GB) | Índices (GB) | Total (GB) | Estatística | Uso | Para quê |
|---|---:|---:|---:|---:|---:|---|---|---|
| `MATMATERIALMOV` | 12.290.811 | 91 | 3,17 | 6,80 | 9,97 | 2026-10-27 | R | Movimentação de material (consumo por paciente/unidade); tem 31 índices |
| `MATBALANCEHISTORY` | 3.998.901 | 7 | 0,18 | 0,20 | 0,38 | 2026-10-08 | R | Histórico de saldo de estoque |
| `MATDISPENSINGAREA` | 13 | 10 | < 0,01 | < 0,01 | < 0,01 | 2026-10-02 | R | Áreas de dispensação (farmácias / almoxarifados) |

## 4. Cadastros e domínios

| Tabela | Linhas | Colunas | Dados (GB) | Índices (GB) | Total (GB) | Estatística | Uso | Para quê |
|---|---:|---:|---:|---:|---:|---|---|---|
| `GLBENTERPRISE` | 10.704 | 117 | < 0,01 | < 0,01 | < 0,01 | 2026-09-08 | R C Z | Operadoras / convênios e unidades |
| `GLBHEALTHPROVIDER` | 22 | 52 | < 0,01 | < 0,01 | < 0,01 | 2026-10-01 | R C | Unidade prestadora |
| `GLBHEALTHPROVDEP` | 24 | 36 | < 0,01 | < 0,01 | < 0,01 | 2026-07-31 | R C | Setor / departamento da unidade |
| `GLBDEPARTMENT` | 27 | 14 | < 0,01 | < 0,01 | < 0,01 | 2026-06-16 | C | Departamento (pacientes em atendimento) |
| `GLBPATIENT` | 18.107 | 14 | < 0,01 | < 0,01 | < 0,01 | 2026-08-25 | C Z | Paciente → pessoa |
| `GLBPERSON` | 67.893 | 78 | 0,02 | < 0,01 | 0,02 | 2026-08-25 | C Z | Nome do paciente (mascarado na tela) |
| `SCCCODE` | 703.990 | 6 | 0,08 | 0,14 | 0,22 | 2026-06-10 | R C Z | Códigos de item (TUSS, material, procedimento) |
| `SCCTABLE` | 344 | 8 | < 0,01 | < 0,01 | < 0,01 | 2026-03-05 | R C | Tabela de origem do código (categoria) |
| `CTRRESOURCETYPE` | 18 | 9 | < 0,01 | < 0,01 | < 0,01 | 2026-03-05 | C | Tipo de recurso do item |

## 5. Formulários de evolução TD* (acesso dinâmico)

A consulta de evolução não tem uma tabela fixa. Ela lê `GLBTEMPLATE.TABLENAME` da evolução e
faz `SELECT * FROM <TD*> WHERE IDEVOLUTION IN (...)`, com no máximo 1.000 IDs por vez
(`fonte_oracle.rodar_formulario`). Na prática qualquer uma das **71 tabelas TD*** que existem
e têm template pode ser lida: são 2,13 milhões de linhas e cerca de 16,7 GB sem LOBs. O acesso
é sempre por `IDEVOLUTION`, nunca por varredura.

### Quem depende delas

Só **Consultas › Evolução clínica** (`src/consultas/evolucao.py`). Reports, conciliação e
faturamento não leem nenhuma TD*.

Se a tabela de um formulário faltar (não existe, sem grant ou não replicada):

- **Continua funcionando:** a lista de evoluções (data, profissional, tipo, que vem de
  `CAPEVOLUTION`), as pendências (intercorrência ou prescrição sem evolução, última evolução
  médica) e os dados que cada tipo de atendimento usa: internações em 90 dias (home care),
  dias internado (transição) e sessões da agenda (ambulatório).
- **Deixa de funcionar:** o conteúdo da ficha (sinais vitais, escalas, anotações). A tela
  mostra o alerta "Formulários sem conteúdo legível" e a IA não lê essas evoluções. A leitura
  clínica (tendência, risco de internação, meta) fica só com metadados e contagens, e tende
  a sair "indeterminado".

### Prioridade

Ordenadas pelo volume de evoluções dos últimos 12 meses (`CAPEVOLUTION` × `GLBTEMPLATE`).

**Essenciais.** São três tabelas com 572 mil evoluções/ano (89% das 14 tabelas listadas aqui)
e ~11,1 GB. Sem elas, a leitura clínica de home care e de internação some:

| Tabela | Evoluções 12m | Linhas | Colunas | Dados (GB) | Índices (GB) | Total (GB) | Estatística |
|---|---:|---:|---:|---:|---:|---:|---|
| `TDWD_VISITAS_HC` † | 329.843 | 988.626 | 998 | 7,33 | 0,09 | 7,43 | 2026-09-21 |
| `TDWD_VISITAS_HSP` † | 134.353 | 188.376 | 998 | 3,49 | 0,01 | 3,51 | 2026-08-29 |
| `TDWD_ANOTENF_HSP` | 107.991 | 128.976 | 70 | 0,19 | < 0,01 | 0,20 | 2026-09-30 |

**Recomendadas.** São 11 tabelas com 69 mil evoluções/ano e só ~0,25 GB no total. O custo é
baixo e elas completam a evolução livre, a coordenação (fisio, médica, fono), a monitoria e
as escalas:

| Tabela | Evoluções 12m | Linhas | Colunas | Dados (GB) | Índices (GB) | Total (GB) | Estatística |
|---|---:|---:|---:|---:|---:|---:|---|
| `TD_EVOL_LIVRE_HSP` † | 17.604 | 33.265 | 8 | 0,02 | < 0,01 | 0,02 | 2026-09-23 |
| `TD_COORD_FISIO` | 10.997 | 27.181 | 128 | 0,03 | < 0,01 | 0,04 | 2026-09-16 |
| `TD_EVOLUCAO_LIVRE` | 9.152 | 22.500 | 11 | 0,02 | < 0,01 | 0,02 | 2026-07-24 |
| `TD_FOLLOWUP_MONIT` | 8.109 | 30.737 | 42 | 0,01 | < 0,01 | 0,02 | 2026-08-18 |
| `TDWD_MONIT` | 6.415 | 7.297 | 163 | < 0,01 | < 0,01 | < 0,01 | 2026-08-26 |
| `TD_COORD_MED` | 5.188 | 16.545 | 95 | 0,06 | < 0,01 | 0,06 | 2026-09-18 |
| `TD_COORD_FONO` | 3.679 | 9.003 | 157 | 0,01 | < 0,01 | 0,01 | 2026-07-08 |
| `TDWD_PLENO` | 2.813 | 3.490 | 307 | 0,03 | < 0,01 | 0,03 | 2026-08-13 |
| `TDAVAD_SCORE` | 2.447 | 7.960 | 98 | < 0,01 | < 0,01 | < 0,01 | 2026-05-19 |
| `TDWD_ADM_HSP` † | 1.876 | 2.846 | 604 | 0,03 | < 0,01 | 0,03 | 2026-08-31 |
| `TDWD_CASSI` | 824 | 1.153 | 144 | < 0,01 | < 0,01 | < 0,01 | 2026-09-29 |

**Não precisam agora:**

- **`TDWD_VISITAS_HC3`**: ~5,2 GB e 612 mil linhas, com 462 mil evoluções históricas e
  **nenhuma nos últimos 12 meses**. Só seria lida ao abrir uma competência antiga. É a maior
  economia possível: quase um terço do volume da seção.
- **As outras 57 TD***: cada uma tem menos de 1.000 evoluções por ano e, somadas, ficam em
  torno de 0,1 GB. A falta de uma delas só tira o conteúdo daquele formulário específico. Dá
  para incluir sob demanda, quando o alerta da tela mostrar o nome dela.

**Pendente (não existe hoje):** `TDWD_AMBULATORIO` está cadastrada no template (ficha
"AMB - Ficha Diária Fisio-Premier"), com 1.284 evoluções em 12 meses, mas **não existe no
schema** (ORA-00942). Por isso a ficha do ambulatório fica sem conteúdo e a meta da
reabilitação é avaliada só pela agenda (`CAPCONSULT`). A pendência está com o TI.

## 6. Proposta para o BigQuery: particionamento e cluster

Proposta montada a partir dos filtros e joins que as SQLs de `sql_oracle.py` fazem hoje e
que o futuro `sql_bq.py` vai repetir. Os tamanhos são os do Oracle; no BigQuery o tamanho
lógico muda (INT64 = 8 bytes, NUMERIC = 16, STRING = 2 + texto) e os 11 GB de índices
deixam de existir.

### Critérios

- **Volume pequeno.** Todas as tabelas fixas somam ~10 GB de dados. No BigQuery a consulta
  cobra os bytes **das colunas lidas**, com mínimo de 10 MB por tabela. Abaixo de ~100 MB,
  particionar ou clusterizar não reduz custo nenhum. Essas tabelas ficam **sem nada**.
- **Partição mensal, nunca diária.** Os filtros são por competência ou por período de
  relatório, de um mês ou mais. A partição diária geraria milhares de partições de poucos MB.
  A mensal fica em algumas centenas e também é a unidade natural de recarga.
- **Partição só onde o filtro de data é direto na tabela.** O BigQuery não poda a partição
  de uma tabela a partir do filtro feito em outra tabela do join. Hoje `CAPPAYMENTITEM` só é
  filtrada por período via `CAPPAYMENT.STARTDATE`. Para particionar o item, a carga precisa
  **trazer a competência da conta para dentro do item** (coluna `COMPETENCIA`).
- **Cluster pelas chaves de lookup e de join.** São `IDPAYMENT`, `IDBUDGET`, `IDADMISSION`
  e `IDEVOLUTION`. O cluster também poda blocos em `IN (...)` e `=`, sem filtro de data.
- **Unidade por ID, não por nome.** Os filtros de unidade comparam
  `UPPER(TRIM(hc.NAME))` depois do join, e assim nenhum cluster é aproveitado. No
  `sql_bq.py`, resolver o nome para o ID (`IDHOMECARE` / `IDHEALTHPROVIDER`) antes e
  filtrar a tabela de fato pelo ID.
- **Recarga por partição.** O ERP altera linhas antigas: a glosa chega meses depois, a
  conta é reaberta, o item é estornado. Em vez de `MERGE`, a carga regrava as partições dos
  últimos N meses com `WRITE_TRUNCATE` no decorador (`tabela$202610`). As tabelas sem
  partição, que são pequenas, são recarregadas inteiras.
- **Tipos.** `DATE` do Oracle vira `DATETIME` (tem hora), e o particionamento usa
  `DATETIME_TRUNC(col, MONTH)`. Linhas com data nula vão para a partição `__NULL__`.

### Faturamento, orçamento e auditoria

| Tabela | Partição | Cluster | Colunas a criar na carga | Por quê |
|---|---|---|---|---|
| `CAPPAYMENT` | — | — | `COMPETENCIA` = `DATE_TRUNC(STARTDATE, MONTH)` | 0,01 GB. É dela que a competência desce para os itens |
| `CAPPAYMENTITEM` | `COMPETENCIA` (mês) | `IDPAYMENT`, `IDBUDGET`, `IDADMISSION` | `COMPETENCIA`, `IDHOMECARE` e `SIMULATION`, vindos da conta | Toda a cascata, glosa e pré-auditoria filtram por competência e unidade. Os lookups por conta (`IDPAYMENT IN`), orçamento (`IDBUDGET = :ID`, `NOT EXISTS`) e admissão usam o cluster. **Sem** `require_partition_filter`, porque os lookups por ID não têm data |
| `CAPPAYMENTITEMWORK` | `COMPETENCIA` (mês) | `IDPAYMENT`, `IDADMISSION` | `COMPETENCIA`, vinda da conta | É a maior tabela de faturamento (4,4 GB) e só serve ao cruzamento por protocolo, que entra por `IDPAYMENT`. A partição serve para recarregar só os meses abertos. Avaliar carregar só os últimos 24 meses: na base de set/2026, só 11 linhas casaram por ela |
| `CAPBUDGET` | — | — | `SENHA` = `TRIM(AUTHORIZEXTCODE)` | 0,03 GB. A busca por senha do TISS fica direta, sem `TRIM` na consulta |
| `CAPBUDGETITEM` | — | `IDBUDGET` | — | 0,39 GB, lida sempre por `IDBUDGET` (valor orçado, itens do orçamento) e nunca por data |
| `CAPADMISSION` † | — | — | — | 0,02 GB. Entrada e saída formam um intervalo aberto, que não dá para particionar. Carregar só as colunas usadas e deixar de fora o CLOB e boa parte das 194 colunas |
| `TTMPAUDITBILLCTR` | — | `IDHOMECARE`, `TRANSKEY` | — | 0,18 GB. A consulta pega `MAX(TRANSKEY)` por unidade. Alternativa melhor: carregar só a última execução de cada unidade |

### Assistencial

| Tabela | Partição | Cluster | Por quê |
|---|---|---|---|
| `CAPEVOLUTION` | `STARTDATE` (mês) | `IDADMISSION`, `IDTEMPLATE` | Todas as leituras têm janela de `STARTDATE`, que vai do período −1 a +2 dias, e entram por admissão. **Sem** `require_partition_filter`: os `EXISTS` de intercorrência e prescrição filtram a data relativa à outra tabela (`e.STARTDATE >= TRUNC(i.STARTDATE)`), e isso não conta como filtro de partição |
| `CAPCONSULT` | `AGENDASTARTDATE` (mês) | `IDADMISSION` | São 3,5 milhões de linhas e 99 colunas, lidas sempre por admissão e período da agenda. Pode ter `require_partition_filter = TRUE` |
| `CAPPRESCRIPTION` | — | — | 0,02 GB |
| `CAPINTERCURRENT` † | — | — | 0,04 GB |
| `CAPINTERCURRENTCFG`, `CAPINTERCLASSIF`, `GLBTEMPLATE`, `GLBTEMPLATEVAR` | — | — | Domínios com menos de 5 mil linhas |

### Materiais e medicamentos

| Tabela | Partição | Cluster | Colunas a criar na carga | Por quê |
|---|---|---|---|---|
| `MATMATERIALMOV` | `MOVDATE` (mês) | `MOVTYPE`, `IDDISPENSINGAREA`, `SCMATERIAL` | `IDADMISSION` = `COALESCE(IDADMISSIONDEST, IDADMISSIONSOURCE)` | É a maior tabela fixa: 3,2 GB de dados e mais 6,8 GB de índices que deixam de existir. Todo consumo filtra período e `MOVTYPE` (11, 14 e 15), e o estoque agrupa por área. A coluna derivada evita o join por `NVL(...)`. Pode ter `require_partition_filter = TRUE` |
| `MATBALANCEHISTORY` | `REFERENCEDATE` (mês) | `REFERENCEDATE`, `IDDISPENSINGAREA` | — | É a foto diária do saldo e a consulta lê uma data só, a última antes do fim do período. A partição mensal mais o cluster pela data leem só aquele dia |
| `MATDISPENSINGAREA` | — | — | — | 13 linhas |

### Cadastros e domínios

Nenhuma tem partição nem cluster. A maior é `SCCCODE`, com 0,08 GB. Juntas somam menos de
0,3 GB e são recarregadas inteiras a cada carga.

### Formulários TD*

O acesso é `SELECT * ... WHERE IDEVOLUTION IN (...)`. **No BigQuery, isso é caro se for
copiado como está**: `SELECT *` lê todas as colunas, e `TDWD_VISITAS_HC` tem 998 colunas e
7,3 GB. Sem cluster, cada abertura de evolução varreria a tabela inteira.

| Tabela | Partição | Cluster | Colunas a criar na carga |
|---|---|---|---|
| `TDWD_VISITAS_HC` †, `TDWD_VISITAS_HSP` †, `TDWD_ANOTENF_HSP` (essenciais) | `DT_EVOLUCAO` (mês) | `IDEVOLUTION` | `DT_EVOLUCAO` = `CAPEVOLUTION.STARTDATE` da evolução |
| As 11 recomendadas e as demais TD* | — | `IDEVOLUTION` | — |

- O cluster por `IDEVOLUTION` já reduz a leitura aos blocos daquelas evoluções. A partição
  por `DT_EVOLUCAO` corta ainda mais, mas só funciona se o `rodar_formulario` do BigQuery
  receber o período, que a tela de evolução já conhece, e filtrar
  `DT_EVOLUCAO BETWEEN ...` junto com o `IN`.
- Nas tabelas pequenas o cluster não muda o custo, mas deixa a carga genérica: o mesmo
  `CLUSTER BY IDEVOLUTION` para todas as TD*.
- Para as duas de 998 colunas, vale trocar o `SELECT *` pelas colunas que têm rótulo em
  `GLBTEMPLATEVAR`. É o que mais reduz bytes lidos, mais do que qualquer partição.
- No dry-run, o custo estimado de tabela clusterizada é o teto, a varredura total. O valor
  cobrado de fato sai menor.

### Exemplo de DDL

```sql
CREATE TABLE erp.CAPPAYMENTITEM (
  ID INT64, IDPAYMENT INT64, IDBUDGET INT64, IDADMISSION INT64,
  COMPETENCIA DATE,            -- DATE_TRUNC(CAPPAYMENT.STARTDATE, MONTH), gravada na carga
  IDHOMECARE INT64, SIMULATION INT64,
  -- ... demais colunas
)
PARTITION BY COMPETENCIA      -- coluna DATE já truncada no mês: 1 partição por competência
CLUSTER BY IDPAYMENT, IDBUDGET, IDADMISSION;

CREATE TABLE erp.MATMATERIALMOV ( ... )
PARTITION BY DATETIME_TRUNC(MOVDATE, MONTH)
CLUSTER BY MOVTYPE, IDDISPENSINGAREA, SCMATERIAL
OPTIONS (require_partition_filter = TRUE);
```

`PARTITION BY COMPETENCIA` com coluna `DATE` cria partição **diária**. Como a coluna já
vem truncada no mês, só o dia 1 recebe linhas e o efeito é de uma partição por mês. O
equivalente explícito é `PARTITION BY DATE_TRUNC(COMPETENCIA, MONTH)`, que é o que se usa
se a coluna guardar a data cheia.

### Resumo

| | Tabelas |
|---|---|
| Partição mensal + cluster | `CAPPAYMENTITEM`, `CAPPAYMENTITEMWORK`, `CAPEVOLUTION`, `CAPCONSULT`, `MATMATERIALMOV`, `MATBALANCEHISTORY`, `TDWD_VISITAS_HC`, `TDWD_VISITAS_HSP`, `TDWD_ANOTENF_HSP` |
| Só cluster | `CAPBUDGETITEM`, `TTMPAUDITBILLCTR`, demais TD* |
| Nada (pequenas) | `CAPPAYMENT`, `CAPBUDGET`, `CAPADMISSION`, `CAPPRESCRIPTION`, `CAPINTERCURRENT`, todos os cadastros e domínios |

## Citadas no código, mas não consultadas

Estas aparecem só em comentários de `sql_oracle.py`. Nenhuma SQL as lê hoje:

| Tabela | Linhas | Observação |
|---|---:|---|
| `FINRECOGBILL` | 3.846 | NF no financeiro; a NF é lida direto de `CAPPAYMENT.BSNUMBER/BSSERIAL` |
| `FINRECOGBILLPAYM` | 4.793 | Vínculo NF × conta |
| `GLBTEXT` | 2.881.924 | Texto livre de evolução (~3,8 GB alocados); cobre só ~1% das evoluções |

## Como reproduzir

As consultas de dicionário usadas (rodar com o usuário da aplicação):

```sql
SELECT TABLE_NAME, NUM_ROWS, AVG_ROW_LEN, BLOCKS, LAST_ANALYZED
  FROM ALL_TABLES WHERE OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA');

SELECT TABLE_NAME, SUM(LEAF_BLOCKS) AS LEAF_BLOCKS, COUNT(*) AS N_INDICES
  FROM ALL_INDEXES WHERE OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA')
 GROUP BY TABLE_NAME;

SELECT TABLE_NAME, COLUMN_NAME
  FROM ALL_LOBS WHERE OWNER = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA');
```

Para ter o tamanho físico exato, incluindo LOBs, um DBA precisa rodar
`SELECT SEGMENT_NAME, SEGMENT_TYPE, SUM(BYTES) FROM DBA_SEGMENTS WHERE OWNER = '<schema>' GROUP BY ...`
juntando os segmentos de LOB por `DBA_LOBS.SEGMENT_NAME`.
