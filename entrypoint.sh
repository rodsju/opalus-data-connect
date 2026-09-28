#!/usr/bin/env sh
set -e

echo ">>> Entrypoint iniciado (ENV=$ENV, SA_KEY_FILE=$SA_KEY_FILE, PROJECT_ID=$PROJECT_ID)"
echo ">>> VARS ($ENV, $SA_KEY_FILE, $PROJECT_ID)"
# Só faz a checagem de key se não estiver em PRD
if [ "$ENV" = "hml" ]; then

  if [ ! -f "$SA_KEY_FILE" ]; then
    echo "⚠️  AVISO: SA key não encontrada em $SA_KEY_FILE"
    echo "⚠️ ADC não encontrado, rode: gcloud auth application-default login --project=$PROJECT_ID"
  else
    echo "✅ Usando SA key em $SA_KEY_FILE"

    # O ADC nao guarda o e-mail da conta (o campo "account" vem vazio), entao o
    # quota_project_id e a unica pista offline de em qual contexto ele foi
    # cunhado. Divergiu do PROJECT_ID, provavelmente e ADC de outra conta.
    # `|| echo ""` porque o `set -e` mataria o boot se o parse falhasse.
    QUOTA=$(python -c 'import json,sys; print(json.load(open(sys.argv[1])).get("quota_project_id",""))' "$SA_KEY_FILE" 2>/dev/null || echo "")

    if [ -z "$QUOTA" ]; then
      echo "ℹ️  ADC sem quota_project_id gravado — nao da para conferir o projeto."
    elif [ "$QUOTA" != "$PROJECT_ID" ]; then
      echo "⚠️  ADC cunhado para o projeto '$QUOTA', mas este ambiente e '$PROJECT_ID'."
      echo "⚠️  Isso costuma significar ADC de outra conta. As paginas de dados vao dar 502."
      echo "⚠️  Rode no host: gcloud auth application-default login <sua-conta> --project=$PROJECT_ID"
    else
      echo "✅ ADC casa com o projeto: $QUOTA"
    fi

    export GOOGLE_APPLICATION_CREDENTIALS="$SA_KEY_FILE"
    export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
  fi
  
else
  echo "ℹ️  Ambiente Cloud detectado — ignorando checagem de SA_KEY_FILE"
fi

exec "$@"
