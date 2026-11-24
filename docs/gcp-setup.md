# Setup no GCP — atlas-connect

O que precisa existir no GCP antes do primeiro deploy, e o que se faz uma vez
depois dele. O workflow (`.github/workflows/deploy-{hml,prd}.yaml`) só builda,
publica a imagem e faz o `gcloud run deploy`: nada daqui roda sozinho.

Segue o padrão do `opalus-atlas-control-app` (`docs/gcp-setup.md` de lá). A
**infra do projeto**, criada uma vez para todas as apps do Atlas, está documentada
lá e **não se repete aqui**: instância Cloud SQL `atlas-pg` (sem IP público, PSC
para as apps, login IAM ligado), endpoint PSC e o nome `atlas-pg.atlas.internal`,
VPC `atlas-vpc` e `atlas-services-subnet`, repositório `atlas-ar-apps`, pool e
provider de Workload Identity e a SA de deploy `atlas-github-deploy` com seus
papéis. Confira tudo isso antes de começar (passo 0).

Em hml o app também alcança o **Oracle do IW pela VPN** do projeto (seção 8).

Este app é **dono de duas coisas que o `opalus-atlas-dash-app` também usa**:

- o database `atlas-connect`, onde fica `catalogo.provedor_ia` (o dash lê só essa tabela);
- a senha `IA_SENHA_MESTRA`, que cifra as chaves dos provedores. Os dois apps precisam da mesma senha (secret do GitHub em cada repo, passo 3).

Por isso este setup vem **antes** do setup do dash.

```bash
# hml
export PROJECT=atlas-dw-hml-511718
export REGION=us-central1
# prd
# export PROJECT=atlas-dw-prd-511718
# export REGION=southamerica-east1

export SERVICE=atlas-connect
export INSTANCE=atlas-pg
export DB=atlas-connect
export SA_NAME=atlas-app-connect
export SA=${SA_NAME}@${PROJECT}.iam.gserviceaccount.com
# o usuario IAM no Postgres e o e-mail da SA sem ".gserviceaccount.com"
export DB_USER=${SA_NAME}@${PROJECT}.iam
export DEPLOY_SA=atlas-github-deploy@${PROJECT}.iam.gserviceaccount.com
# O repo fica na conta rodsju, nao na org saudeopalus: o provider do WIF tem uma
# excecao so para ele (passo 4)
export GH_ORG=rodsju
export GH_REPO=opalus-data-connect
export POOL_ID=atlas-github-pool          # prd: CONFERIR
export PROVIDER_ID=github                 # prd: CONFERIR
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
# bucket temporario para importar o catalogo local no Cloud SQL (passo 5)
export BUCKET=atlas-datalake-raw-hml   # bucket do datalake, COMPARTILHADO: so cp/rm do arquivo; prd: CONFERIR
```

---

## 0. Conferir a infra do projeto

```bash
gcloud sql instances describe $INSTANCE --project=$PROJECT \
  --format="value(databaseVersion,settings.ipConfiguration.pscConfig.pscEnabled,settings.databaseFlags)"
gcloud artifacts repositories describe atlas-ar-apps --project=$PROJECT --location=$REGION --format='value(name)'
gcloud iam service-accounts describe $DEPLOY_SA --project=$PROJECT --format='value(email)'
gcloud iam workload-identity-pools providers describe $PROVIDER_ID --project=$PROJECT \
  --location=global --workload-identity-pool=$POOL_ID --format='value(name)'
```

O primeiro comando precisa mostrar `POSTGRES_16`, `True` e `cloudsql.iam_authentication` com o valor `on`.
Se algum dos quatro comandos falhar, siga o `docs/gcp-setup.md` do `opalus-atlas-control-app`
(passos 2.1, 3.2 e 3.3) antes de continuar.

## 1. APIs

```bash
gcloud services enable secretmanager.googleapis.com sqladmin.googleapis.com \
  run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com \
  --project=$PROJECT
```

## 2. Service account de runtime

> `--format=none`: sem ele, cada `add-iam-policy-binding` imprime a política
> inteira do projeto. O comando só acrescenta o papel.

Em hml a SA `atlas-app-connect` **já existe**, sem papéis, e foi a usada no teste de
conexão com o Oracle. Pule o `create` e siga com os papéis.

```bash
gcloud iam service-accounts create $SA_NAME --project=$PROJECT \
  --display-name="Cloud Run atlas-connect"
until gcloud iam service-accounts describe $SA --project=$PROJECT >/dev/null 2>&1; do sleep 5; done
sleep 30

# Login IAM no Cloud SQL
for ROLE in roles/cloudsql.client roles/cloudsql.instanceUser; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member=serviceAccount:$SA --role=$ROLE --condition=None --format=none
done

# A SA de deploy precisa rodar o servico como esta SA
gcloud iam service-accounts add-iam-policy-binding $SA --project=$PROJECT \
  --member=serviceAccount:$DEPLOY_SA --role=roles/iam.serviceAccountUser --format=none
```

## 3. Senha mestra `IA_SENHA_MESTRA` (compartilhada com o dash)

Fica num **secret do GitHub** (`IA_SENHA_MESTRA` em hml, `IA_SENHA_MESTRA_PRD` em
prd), e o workflow passa o valor como variável de ambiente no `gcloud run deploy`.
Não usamos o Secret Manager para ela: o secret `ia-senha-mestra` não existe no
projeto, e o deploy falhava com `Permission denied on secret`. O dash faz igual.

Use a **mesma** `IA_SENHA_MESTRA` do `.env` local (e do dash). As chaves dos
provedores foram cifradas com ela, e com outra senha o `pgp_sym_decrypt` recusa.
Cadastre em Settings → Secrets and variables → Actions do repo, junto com os do passo 4.

## 4. GitHub Actions: liberar o repositório e os secrets

O pool, o provider e os papéis da SA de deploy já existem (passo 0).

**Este repositório não está na org `saudeopalus`**, e sim em `rodsju`. O
`attribute-condition` do provider aceita a org inteira e, fora dela, só exceções
nomeadas, presas ao `repository_owner_id` da conta (`80115618`). Em hml a exceção já
foi incluída (feito em 14/11/2026, junto com o binding abaixo):

```bash
gcloud iam workload-identity-pools providers update-oidc $PROVIDER_ID --project=$PROJECT \
  --location=global --workload-identity-pool=$POOL_ID \
  --attribute-condition="(assertion.repository_owner == 'saudeopalus' && assertion.repository_owner_id == '339797207') || (assertion.repository == 'rodsju/opalus-atlas-dash-app' && assertion.repository_owner_id == '80115618') || (assertion.repository == 'rodsju/opalus-data-connect' && assertion.repository_owner_id == '80115618')"
```

O `update-oidc` **substitui** a condição inteira. Antes de rodar, confira a atual com
`providers describe` e mantenha o que já existe. Se o repo for para a org
`saudeopalus`, a exceção deixa de ser necessária.

Liberar o repositório na SA de deploy:

```bash
gcloud iam service-accounts add-iam-policy-binding $DEPLOY_SA --project=$PROJECT \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GH_ORG}/${GH_REPO}" \
  --format=none

# hml; em prd, os mesmos comandos com as variaveis de prd e o sufixo _PRD no nome
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo=$GH_ORG/$GH_REPO --body="$(
  gcloud iam workload-identity-pools providers describe $PROVIDER_ID --project=$PROJECT \
    --location=global --workload-identity-pool=$POOL_ID --format='value(name)')"
gh secret set GCP_DEPLOY_SERVICE_ACCOUNT --repo=$GH_ORG/$GH_REPO --body="$DEPLOY_SA"
```

Sem GitHub environment, qualquer branch lê os secrets de prd: proteja a `main`.

## 5. Database, usuário IAM e o catálogo

### 5.1 Database e usuário

```bash
gcloud sql databases create $DB --instance=$INSTANCE --project=$PROJECT
gcloud sql users create $DB_USER --instance=$INSTANCE --project=$PROJECT \
  --type=cloud_iam_service_account
```

### 5.2 Schema e extensões (uma vez, como `postgres`)

`vector` e `pgcrypto` só são criadas por `cloudsqlsuperuser`. As duas ficam **dentro do
schema `catalogo`**, como no banco local: o dump usa o tipo `catalogo.vector`, e
importar com as extensões em `public` falha com `type "catalogo.vector" does not
exist`. Abra o **Cloud SQL Studio** (console → SQL → `atlas-pg` → Cloud SQL Studio)
como `postgres`, **no database `atlas-connect`**:

```sql
CREATE SCHEMA catalogo;
CREATE EXTENSION vector WITH SCHEMA catalogo;
CREATE EXTENSION pgcrypto WITH SCHEMA catalogo;
```

Se não souber a senha do `postgres`: `gcloud sql users set-password postgres
--instance=$INSTANCE --project=$PROJECT --prompt-for-password`.

### 5.3 Importar o catálogo local

O catálogo foi gerado **localmente** pelo `scripts/mapear_oracle.py`. Importar
evita remapear do zero: o mapeamento leva horas, e as descrições e os vetores de IA
custam dinheiro. O catálogo tem cerca de 1 GB por causa das amostras e dos vetores, então a importação vai pelo
Cloud Storage com `gcloud sql import`, sem precisar de IP público.

O `sed` tira duas linhas do dump:
- **`SET transaction_timeout`:** o Postgres local é 17 e a `atlas-pg` é 16. O
  `pg_dump` 17 escreve essa linha, e o 16 não reconhece o parâmetro.
- **`CREATE SCHEMA catalogo`:** o schema já foi criado no 5.2, junto com as extensões.

Esse caminho foi ensaiado num Postgres 16 com pgvector: a importação, a troca de dono
do 5.4, a busca vetorial e o DDL reaplicado pela SA funcionaram.

```bash
# No host, com o compose do data-connect de pe
docker exec opalus-catalogo-db pg_dump -U catalogo -d catalogo -n catalogo \
  --no-owner --no-acl \
  | sed -e '/^SET transaction_timeout/d' -e '/^CREATE SCHEMA catalogo;$/d' > catalogo.sql

# O bucket ja existe (e do datalake): nao crie nem apague o bucket
gcloud storage cp catalogo.sql gs://$BUCKET/

# A SA do Cloud SQL le o arquivo do bucket. Em hml ja foi dado no setup do dash;
# rodar de novo nao muda nada
CSQL_SA=$(gcloud sql instances describe $INSTANCE --project=$PROJECT --format='value(serviceAccountEmailAddress)')
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$CSQL_SA --role=roles/storage.objectViewer --format=none

gcloud sql import sql $INSTANCE gs://$BUCKET/catalogo.sql --project=$PROJECT \
  --database=$DB --user=postgres --quiet
```

### 5.4 O app vira dono do schema (uma vez, como `postgres`)

A importação foi feita como `postgres`, então o schema e as tabelas pertencem a ele.
O app grava descrições, vetores e provedores, e o `--somente-ddl` aplica `ALTER`,
que só o dono pode rodar. No Cloud SQL Studio, no database `atlas-connect`,
**troque o projeto pelo do ambiente**:

```sql
-- CREATE SCHEMA IF NOT EXISTS (no DDL) confere este privilegio antes de ver
-- que o schema ja existe
GRANT CREATE ON DATABASE "atlas-connect" TO "atlas-app-connect@atlas-dw-hml-511718.iam";
-- O codigo chama pgp_sym_decrypt e usa o tipo vector sem o schema na frente.
-- No local isso resolve porque o usuario se chama "catalogo" e o search_path
-- padrao e "$user"; o usuario IAM tem outro nome.
ALTER ROLE "atlas-app-connect@atlas-dw-hml-511718.iam" IN DATABASE "atlas-connect"
  SET search_path = catalogo, public;
GRANT "atlas-app-connect@atlas-dw-hml-511718.iam" TO postgres;

DO $$
DECLARE
  dono text := 'atlas-app-connect@atlas-dw-hml-511718.iam';
  r record;
BEGIN
  EXECUTE format('ALTER SCHEMA catalogo OWNER TO %I', dono);
  FOR r IN SELECT c.relname, c.relkind FROM pg_class c
             JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'catalogo' AND c.relkind IN ('r', 'p', 'v', 'm') LOOP
    EXECUTE format('ALTER %s catalogo.%I OWNER TO %I',
      CASE r.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' ELSE 'TABLE' END,
      r.relname, dono);
  END LOOP;
END $$;
```

As sequências e os índices ligados às tabelas mudam de dono junto com elas.

Conferência: tem que aparecer só o usuário da SA.

```sql
SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'catalogo';
```

**Depois do 5.4, rode a parte "No database `atlas-connect`" do passo 2.3 do setup do
dash** (`GRANT CONNECT`, `USAGE` e `SELECT` em `provedor_ia`, e o `search_path`).
Enquanto o database não existe, o dash sobe, mas o check "AI Providers" do `/health`
dele fica vermelho.

Para atualizar o catálogo na nuvem depois de remapear localmente, repita o 5.3
num database vazio. Também dá para apagar antes o schema com
`DROP SCHEMA catalogo CASCADE`, mas **isso apaga os provedores de IA cadastrados na
nuvem**. Depois, refaça o 5.4 e as permissões do dash (passo 2.3 do setup do dash).

```bash
gcloud storage rm gs://$BUCKET/catalogo.sql   # SO o arquivo: o bucket e do datalake
rm catalogo.sql
```

## 6. Primeiro deploy

Faça push na branch do ambiente: `hml` vai para hml, e `main` vai para prd. Depois:

```bash
gcloud run services logs read $SERVICE --project=$PROJECT --region=$REGION --limit=50
export URL=$(gcloud run services describe $SERVICE --project=$PROJECT --region=$REGION --format='value(status.url)')
```

| No log | Confira |
|---|---|
| `could not translate host name` | zona `atlas.internal.` ligada à `atlas-vpc` (passo 3.3 do control) |
| `connection timeout` | `VPC_NETWORK`/`VPC_SUBNET` e o endpoint PSC `ACCEPTED` |
| `password authentication failed` / `IAM authentication failed` | `cloudsql.iam_authentication`, `roles/cloudsql.instanceUser` e o usuário na URI (`atlas-app-connect%40<projeto>.iam`) |
| `permission denied for schema catalogo` | o passo 5.4 |
| `Senha mestra não configurada` | o secret `IA_SENHA_MESTRA` do GitHub (passo 3) |
| `Não conseguimos decifrar a chave` | o secret tem uma senha diferente da que cifrou os provedores importados |
| `/health`: Oracle com `DPY-6005` / timeout | `VPC_SUBNET` precisa ser a `atlas-psc-subnet` (seção 8) e o túnel precisa estar `ESTABLISHED` |
| `/health`: Oracle com `ORA-01017` | o secret `atlas-iw-oracle-ds-iw-password` e o `ORACLE_USER` (`DS_IW`) |
| `/health`: Oracle com `DPY-3001` / erro de criptografia nativa | o NNE virou obrigatório no Oracle (seção 8) |

## 7. Load balancer

O serviço é `--ingress=internal-and-cloud-load-balancing`. Mesma receita do passo 5 do control.
O DNS `*.atlas-hml.saudeopalus.com` e o certificado wildcard já existem.

```bash
export HOST=connect.atlas-hml.saudeopalus.com   # prd: CONFERIR
export URL_MAP=atlas-lb-https
export NEG=atlas-neg-connect
export BACKEND=atlas-bs-connect
export PATH_MATCHER=pm-connect

gcloud compute url-maps export $URL_MAP --project=$PROJECT --global --destination=url-map-antes.yaml

gcloud compute network-endpoint-groups create $NEG --project=$PROJECT \
  --region=$REGION --network-endpoint-type=serverless --cloud-run-service=$SERVICE
gcloud compute backend-services create $BACKEND --project=$PROJECT --global \
  --load-balancing-scheme=EXTERNAL_MANAGED --enable-logging --logging-sample-rate=1.0
gcloud compute backend-services add-backend $BACKEND --project=$PROJECT --global \
  --network-endpoint-group=$NEG --network-endpoint-group-region=$REGION
gcloud compute backend-services update $BACKEND --project=$PROJECT --global \
  --custom-response-header='Strict-Transport-Security: max-age=31536000; includeSubDomains'
gcloud compute url-maps add-path-matcher $URL_MAP --project=$PROJECT --global \
  --path-matcher-name=$PATH_MATCHER --default-service=$BACKEND --new-hosts=$HOST
```

É o LB, pelo `atlas-auth-lb`, que injeta `x-opalus-user-email`. **Esse header nunca vira
variável de ambiente no Cloud Run**: o fallback de `usuario.identificar()`
autorizaria qualquer request como aquele e-mail.

Se o `atlas-auth-lb` estiver checando rotas pelo snapshot do `atlas-control`
(`PERMISSIONS_URL` ligado), cadastre a app lá antes de abrir o host. Use o slug
`atlas-connect` com a URL `https://$HOST`, as rotas do `layout.MENU` mais
`/static/*`, `/ds-static/*` e `/logout`, e um perfil para quem usa. Sem esse cadastro,
ninguém entra.

## 8. Oracle pela VPN (hml)

O projeto de hml tem uma VPN clássica até o Fortinet da Opalus. Ela é mantida pelo
Terraform da fundação, e **nada aqui a altera**:

| Recurso | O que é |
|---|---|
| `atlas-iw-tunnel-0` (`atlas-vpn-gw`, `us-central1`) | IKEv2 até `4.228.200.96`. Seletores: local `10.40.1.0/24`, remoto `192.168.30.0/24` |
| rota `atlas-iw-route-0` | `192.168.30.0/24` da `atlas-vpc` pelo túnel |
| Datastream `atlas-iw-opalus` | lê o mesmo Oracle (`192.168.30.4:1521/IWTST`, usuário `DS_IW`) e alimenta o `bronze_iw_opalus` do dash |

**Por que a `atlas-psc-subnet`.** Como a VPN é por política, só passa tráfego com
origem na faixa do seletor local, `10.40.1.0/24`, que é a `atlas-psc-subnet`. Saindo
pela `atlas-services-subnet` (`10.40.4.0/22`), a rota leva o pacote até o túnel, mas
ele não passa. Por isso o `deploy-hml.yaml` usa `VPC_SUBNET=atlas-psc-subnet`. O
endpoint PSC do Cloud SQL fica na mesma subnet, então o Postgres continua alcançável.

**Testado:** com a SA `atlas-app-connect` saindo pela `atlas-psc-subnet`, a porta 1521
abriu e o login no Oracle 19.25 funcionou, em **modo thin** do `python-oracledb`, que
é o modo do app.

**Usuário Oracle: `DS_IW`, o mesmo do Datastream.** A senha vem do secret que já
existe para o Datastream, sem cópia:

```bash
gcloud secrets add-iam-policy-binding atlas-iw-oracle-ds-iw-password --project=$PROJECT \
  --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor --format=none
```

Compartilhar o usuário tem custo: se a senha do `DS_IW` for trocada, troque também a
versão do secret, e os **dois** (Datastream e app) passam a usá-la. Se a conta for
bloqueada por tentativas erradas do app, **a replicação para junto**. Se isso
incomodar, peça ao DBA um usuário próprio, só de leitura, e troque `ORACLE_USER` e o
secret no workflow.

**O que roda pela VPN.** No web app, o Oracle ao vivo só aparece no `/health` (check
"Origem (Oracle)"). As páginas leem o catálogo do Postgres. O mapeador
(`scripts/mapear_oracle.py`, `make catalogo`) é um script de linha de comando e
nenhuma rota o dispara. Para rodá-lo na nuvem, o próximo passo é um Cloud Run Job
com a mesma imagem, VPC e secrets. Até lá, ele roda local e a nuvem recebe o
resultado pelo passo 5.3.

**Criptografia nativa (NNE).** O modo thin só fala com o Oracle enquanto a
criptografia nativa (`SQLNET.ENCRYPTION_SERVER`) **não for obrigatória** (`REQUIRED`).
Se o DBA ligar o NNE como obrigatório, o app passa a falhar no login. Há duas saídas:

- **Modo thick:** Instant Client na imagem e `ORACLE_CLIENT_LIB_DIR` apontando para
  ele. O Instant Client precisa de glibc, então a base da imagem sai do Alpine
  (`python:3.11-alpine`) para uma Debian slim.
- **TCPS:** TLS no listener do Oracle, configurado do lado do DBA. O thin continua
  funcionando e a criptografia passa a ser a do TLS.

**prd.** O projeto de prd não tem VPN para o IW, nem a API do Compute ligada. O
`deploy-prd.yaml` sobe sem `ORACLE_*` e pela `atlas-services-subnet`.

## 9. Servidores de origem (Setup › Servidores)

A tela `/setup/servidores` cadastra os servidores de `catalogo.servidor` e os schemas de
cada um. É a origem que o `esquema_id` de cada objeto aponta. O formulário tem o painel
"Conectar no GCP", com os comandos já preenchidos com o projeto e a SA de runtime.

### 9.1 DDL (uma vez por ambiente)

As colunas de credencial vêm do bloco "Credencial do servidor" do
`scripts/catalogo_schema.sql`. Local: `make schema`. Na nuvem, cole **só esse bloco** no
Cloud SQL Studio como `postgres`, no database `atlas-connect`. Funciona porque o
`postgres` é membro do papel da SA, que é a dona das tabelas (passo 5.4). Sem o DDL, a
tela mostra `column "usuario" does not exist`.

**O pré-filtro de schema também muda o DDL.** As quatro views (`vw_dicionario`,
`vw_relacionamentos`, `vw_resumo` e `vw_orfas`) ganharam a coluna `esquema_id`, e os
índices `relacionamento_esquema_origem_idx` e `relacionamento_esquema_destino_idx`
foram criados. Cole também o bloco "Views" do `scripts/catalogo_schema.sql`. Sem ele,
todas as telas do catálogo dão `column "esquema_id" does not exist`. O mais simples é
colar o arquivo inteiro, que pode ser reaplicado.

### 9.2 Dois perfis por servidor: Local e GCP

O mesmo Oracle é acessado com credenciais diferentes em cada lugar, então cada servidor
tem dois perfis. O app usa o do ambiente em que roda: **GCP** quando existe `K_SERVICE`
(o Cloud Run define essa variável), **Local** fora dele. A tela marca o perfil em uso, e
cada perfil tem o seu botão de teste.

| Perfil | Usuário (IW) | Fontes da senha aceitas |
|---|---|---|
| Local | o pessoal, entre aspas duplas como no `.env` | variável de ambiente (`ORACLE_PASSWORD` do `.env`), cifrada no banco (`IA_SENHA_MESTRA`) ou Secret Manager (com ADC) |
| GCP (Cloud Run) | `DS_IW` | Secret Manager, lido a cada conexão e **sem redeploy**, ou variável do `--set-secrets` |

Usuário em branco significa perfil não configurado. Cada servidor precisa de pelo
menos um perfil.

Nome curto de secret é resolvido no `PROJECT_ID` do ambiente. Para outro projeto, ou
uma versão fixa, informe `projects/<p>/secrets/<nome>[/versions/<v>]`. A SA de
runtime precisa de `roles/secretmanager.secretAccessor` **em cada secret**. O Secret
Manager responde `403` também quando o secret não existe, então confira os dois.

### 9.3 O Oracle do IW (`192.168.30.4/IWTST`)

O DDL já preenche o perfil GCP com o que o `deploy-hml.yaml` usa: `DS_IW` e o secret
`atlas-iw-oracle-ds-iw-password`, ao qual a SA já tem acesso (seção 8). O perfil Local
fica com a fonte `env ORACLE_PASSWORD` e sem usuário: preencha o seu na tela. Depois,
no Cloud Run, use **Testar perfil GCP**.

### 9.4 Servidor novo

1. **Rede.** O host precisa ser alcançável pela subnet do serviço. Em hml, só a faixa
   `192.168.30.0/24` passa pela VPN, saindo da `atlas-psc-subnet`. Outra rede exige
   rota ou túnel no Terraform da fundação.
2. **Secret e permissão.** Use os comandos do painel "Conectar no GCP" do formulário.
3. **Cadastro e teste.** Preencha o perfil GCP com a fonte Secret Manager e use
   **Testar perfil GCP** no app do Cloud Run.

**Ainda não usam o cadastro:** o mapeador (`scripts/mapear_oracle.py`) e o check
"Origem (Oracle)" do `/health` continuam lendo `ORACLE_*` do ambiente. O teste de
conexão da tela só conhece Oracle.

## Limitações

- **Lote de descrições.** O lote roda num subprocesso dentro da instância
  (`src/lote.py`). O workflow usa `--no-cpu-throttling` e `--max=1`, mas, com
  `--min-instances=0`, uma instância ociosa pode ser desligada no meio de um lote longo.
  Se isso acontecer, retome o lote em Setup › Lote, ou suba `--min-instances` durante o lote.

## Resumo do que o workflow espera

| Variável no workflow | Valor |
|---|---|
| `SERVICE_NAME` | `atlas-connect` |
| `RUNTIME_SERVICE_ACCOUNT` | `atlas-app-connect@<projeto>.iam.gserviceaccount.com` |
| `POSTGRES_DSN` | `postgresql://atlas-app-connect%40<projeto>.iam@atlas-pg.atlas.internal:5432/atlas-connect?sslmode=require` |
| em `--set-env-vars` | `DB_IAM_AUTH=true` (o token da SA vai como senha, `src/catalogo.py`) |
| em `--set-env-vars` (lista `^|^`) | `IA_SENHA_MESTRA` vinda do secret do GitHub (passo 3) |
| em `--set-secrets` (só hml) | `ORACLE_PASSWORD=atlas-iw-oracle-ds-iw-password:latest` (seção 8) |
| `ORACLE_*` (só hml) | `192.168.30.4` / `1521` / `IWTST` / schema `DBIWGERIATRICS` / usuário `DS_IW` |
| `VPC_NETWORK` / `VPC_SUBNET` | `atlas-vpc` / hml: `atlas-psc-subnet` (seletor da VPN, seção 8); prd: `atlas-services-subnet` |
| `IMAGE` | `<região>-docker.pkg.dev/<projeto>/atlas-ar-apps/atlas-connect` |
| secrets (hml) | `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT` (passo 4), `IA_SENHA_MESTRA` (passo 3) |
| secrets (prd) | os mesmos com `_PRD` |
