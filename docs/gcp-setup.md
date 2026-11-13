# Setup no GCP — atlas-data-connect

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

Este app é **dono de duas coisas que o `opalus-atlas-dash-app` também usa**:

- o database `atlas-data-connect`, onde fica `catalogo.provedor_ia` (o dash lê só essa tabela);
- o secret `ia-senha-mestra`, que cifra as chaves dos provedores. Os dois apps precisam da mesma senha.

Por isso este setup vem **antes** do setup do dash.

```bash
# hml
export PROJECT=atlas-dw-hml-511718
export REGION=us-central1
# prd
# export PROJECT=atlas-dw-prd-511718
# export REGION=southamerica-east1

export SERVICE=atlas-data-connect
export INSTANCE=atlas-pg
export DB=atlas-data-connect
export SA_NAME=atlas-app-data-connect
export SA=${SA_NAME}@${PROJECT}.iam.gserviceaccount.com
# o usuario IAM no Postgres e o e-mail da SA sem ".gserviceaccount.com"
export DB_USER=${SA_NAME}@${PROJECT}.iam
export DEPLOY_SA=atlas-github-deploy@${PROJECT}.iam.gserviceaccount.com
export SECRET=ia-senha-mestra
export GH_ORG=saudeopalus
export GH_REPO=opalus-data-connect
export POOL_ID=atlas-github-pool          # prd: CONFERIR
export PROVIDER_ID=github                 # prd: CONFERIR
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
# bucket temporario para importar o catalogo local no Cloud SQL (passo 5)
export BUCKET=${PROJECT}-atlas-import
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

```bash
gcloud iam service-accounts create $SA_NAME --project=$PROJECT \
  --display-name="Cloud Run atlas-data-connect"
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

## 3. Secret `ia-senha-mestra` (compartilhado com o dash)

Use a **mesma** `IA_SENHA_MESTRA` do `.env` local se for importar o catálogo local
(passo 5). As chaves dos provedores foram cifradas com ela, e com outra senha
o `pgp_sym_decrypt` recusa.

```bash
# Cola a senha e da Ctrl-D: ela nao fica no historico do shell
gcloud secrets create $SECRET --project=$PROJECT --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding $SECRET --project=$PROJECT \
  --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor --format=none
```

O acesso da SA do dash a este secret é dado no setup do dash.

## 4. GitHub Actions: liberar o repositório e os secrets

O pool, o provider e os papéis da SA de deploy já existem (passo 0). Falta só
liberar este repositório:

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
como `postgres`, **no database `atlas-data-connect`**:

```sql
CREATE SCHEMA catalogo;
CREATE EXTENSION vector WITH SCHEMA catalogo;
CREATE EXTENSION pgcrypto WITH SCHEMA catalogo;
```

Se não souber a senha do `postgres`: `gcloud sql users set-password postgres
--instance=$INSTANCE --project=$PROJECT --prompt-for-password`.

### 5.3 Importar o catálogo local

O catálogo é gerado **localmente** pelo `scripts/mapear_oracle.py`, porque o Oracle
só é alcançável pela VPN. O Cloud Run não tem rota até ele (veja a seção Limitações).
Ele tem cerca de 1 GB por causa das amostras e dos vetores, então a importação vai pelo
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

gcloud storage buckets create gs://$BUCKET --project=$PROJECT --location=$REGION \
  --uniform-bucket-level-access
gcloud storage cp catalogo.sql gs://$BUCKET/

# A SA do Cloud SQL le o arquivo do bucket
CSQL_SA=$(gcloud sql instances describe $INSTANCE --project=$PROJECT --format='value(serviceAccountEmailAddress)')
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member=serviceAccount:$CSQL_SA --role=roles/storage.objectViewer --format=none

gcloud sql import sql $INSTANCE gs://$BUCKET/catalogo.sql --project=$PROJECT \
  --database=$DB --user=postgres --quiet
```

### 5.4 O app vira dono do schema (uma vez, como `postgres`)

A importação foi feita como `postgres`, então o schema e as tabelas pertencem a ele.
O app grava descrições, vetores e provedores, e o `--somente-ddl` aplica `ALTER`,
que só o dono pode rodar. No Cloud SQL Studio, no database `atlas-data-connect`,
**troque o projeto pelo do ambiente**:

```sql
-- CREATE SCHEMA IF NOT EXISTS (no DDL) confere este privilegio antes de ver
-- que o schema ja existe
GRANT CREATE ON DATABASE "atlas-data-connect" TO "atlas-app-data-connect@atlas-dw-hml-511718.iam";
-- O codigo chama pgp_sym_decrypt e usa o tipo vector sem o schema na frente.
-- No local isso resolve porque o usuario se chama "catalogo" e o search_path
-- padrao e "$user"; o usuario IAM tem outro nome.
ALTER ROLE "atlas-app-data-connect@atlas-dw-hml-511718.iam" IN DATABASE "atlas-data-connect"
  SET search_path = catalogo, public;
GRANT "atlas-app-data-connect@atlas-dw-hml-511718.iam" TO postgres;

DO $$
DECLARE
  dono text := 'atlas-app-data-connect@atlas-dw-hml-511718.iam';
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

Para atualizar o catálogo na nuvem depois de remapear localmente, repita o 5.3
num database vazio. Também dá para apagar antes o schema com
`DROP SCHEMA catalogo CASCADE`, mas **isso apaga os provedores de IA cadastrados na
nuvem**. Depois, refaça o 5.4 e as permissões do dash (passo 2.3 do setup do dash).

```bash
gcloud storage rm -r gs://$BUCKET   # quando nao precisar mais
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
| `password authentication failed` / `IAM authentication failed` | `cloudsql.iam_authentication`, `roles/cloudsql.instanceUser` e o usuário na URI (`atlas-app-data-connect%40<projeto>.iam`) |
| `permission denied for schema catalogo` | o passo 5.4 |
| `Senha mestra não configurada` | o secret do passo 3 e o `secretAccessor` |
| `Não conseguimos decifrar a chave` | o secret tem uma senha diferente da que cifrou os provedores importados |

## 7. Load balancer

O serviço é `--ingress=internal-and-cloud-load-balancing`. Mesma receita do passo 5 do control.
O DNS `*.atlas-hml.saudeopalus.com` e o certificado wildcard já existem.

```bash
export HOST=connect.atlas-hml.saudeopalus.com   # prd: CONFERIR
export URL_MAP=atlas-lb-https
export NEG=atlas-neg-data-connect
export BACKEND=atlas-bs-data-connect
export PATH_MATCHER=pm-data-connect

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
`atlas-data-connect` com a URL `https://$HOST`, as rotas do `layout.MENU` mais
`/static/*`, `/ds-static/*` e `/logout`, e um perfil para quem usa. Sem esse cadastro,
ninguém entra.

## Limitações

- **Oracle fora de alcance.** O Cloud Run não tem rota até o Oracle (`192.168.30.4`
  só pela VPN). O `/health` mostra as origens Oracle como "Sem configuração",
  porque nenhum `ORACLE_*` vai no deploy. As páginas leem o catálogo no
  Postgres e funcionam. O mapeamento (`make catalogo`, `make amostras`) continua
  **local**, e a nuvem recebe o resultado pelo passo 5.3. Para mapear direto da nuvem,
  seria preciso uma rota da `atlas-vpc` até a rede do Oracle (VPN ou interconnect). CONFERIR.
- **Lote de descrições.** O lote roda num subprocesso dentro da instância
  (`src/lote.py`). O workflow usa `--no-cpu-throttling` e `--max=1`, mas, com
  `--min-instances=0`, uma instância ociosa pode ser desligada no meio de um lote longo.
  Se isso acontecer, retome o lote em Setup › Lote, ou suba `--min-instances` durante o lote.

## Resumo do que o workflow espera

| Variável no workflow | Valor |
|---|---|
| `SERVICE_NAME` | `atlas-data-connect` |
| `RUNTIME_SERVICE_ACCOUNT` | `atlas-app-data-connect@<projeto>.iam.gserviceaccount.com` |
| `POSTGRES_DSN` | `postgresql://atlas-app-data-connect%40<projeto>.iam@atlas-pg.atlas.internal:5432/atlas-data-connect?sslmode=require` |
| em `--set-env-vars` | `DB_IAM_AUTH=true` (o token da SA vai como senha, `src/catalogo.py`) |
| em `--set-secrets` | `IA_SENHA_MESTRA=ia-senha-mestra:latest` (passo 3) |
| `VPC_NETWORK` / `VPC_SUBNET` | `atlas-vpc` / `atlas-services-subnet` |
| `IMAGE` | `<região>-docker.pkg.dev/<projeto>/atlas-ar-apps/atlas-data-connect` |
| secrets (hml) | `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT` (passo 4) |
| secrets (prd) | os mesmos com `_PRD` |
