#!/usr/bin/env bash
# Build and deploy the triage API to Cloud Run.
#
# Usage: infra/deploy-api.sh [IMAGE_TAG]      (default tag: latest)

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-triage-agent-prayag}"
REGION="asia-south1"
SERVICE="triage-api"
TAG="${1:-latest}"
IMAGE="asia-south1-docker.pkg.dev/${PROJECT_ID}/triage/api:${TAG}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaulted, not remembered: --set-env-vars replaces the whole set, so omitting this broke CORS.
DEFAULT_CORS_ORIGINS='["https://support-triage.prayagtushar.xyz","https://support-triage-sigma.vercel.app","http://localhost:5173"]'

echo "Building ${IMAGE}..."
gcloud builds submit "${REPO_ROOT}/api" \
  --config "${REPO_ROOT}/infra/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}" \
  --project "${PROJECT_ID}"

echo "Deploying to ${SERVICE} (${PROJECT_ID}/${REGION})..."

# --no-cpu-throttling: POST /tickets finishes its work after responding, and would stall without it.
# --max-instances 1: the rate limiters are per-process, so a second instance earns 429s.
# --port 8000: the Dockerfile CMD hardcodes it instead of reading $PORT.
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --allow-unauthenticated \
  --platform managed \
  --execution-environment gen2 \
  --service-account "triage-api@${PROJECT_ID}.iam.gserviceaccount.com" \
  --port 8000 \
  --no-cpu-throttling \
  --cpu 1 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 10 \
  --timeout 300 \
  --set-env-vars "APP_ENV=prod,LOG_LEVEL=INFO,CORS_ORIGINS=${CORS_ORIGINS:-${DEFAULT_CORS_ORIGINS}},CLASSIFIER_PROVIDER=openrouter,CLASSIFIER_MODEL=meta-llama/llama-3.3-70b-instruct,DRAFTER_PROVIDER=sarvam,DRAFTER_MODEL=sarvam-105b,JUDGE_PROVIDER=openrouter,JUDGE_MODEL=google/gemini-2.5-flash-lite,EMBEDDING_PROVIDER=openrouter,EMBEDDING_MODEL=openai/text-embedding-3-small,EMBEDDING_DIM=1536,ROUTE_AUTO_REPLY_THRESHOLD=0.90,ROUTE_REVIEW_THRESHOLD=0.55,MAX_TICKETS_PER_DAY=50,LANGFUSE_HOST=https://cloud.langfuse.com,LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}" \
  --set-secrets "DATABASE_URL=triage-database-url:latest,SARVAM_API_KEY=triage-sarvam-key:latest,GEMINI_API_KEY=triage-gemini-key:latest,OPENROUTER_API_KEY=triage-openrouter-key:latest,LANGFUSE_SECRET_KEY=triage-langfuse-secret:latest,DEMO_WRITE_KEY=triage-demo-write-key:latest" \
  --ingress all

echo
echo "Deployed. Smoke test:"
echo "  API=\$(gcloud run services describe ${SERVICE} --region ${REGION} --project ${PROJECT_ID} --format 'value(status.url)')"
echo "  curl -s \"\$API/livez\"   # not /healthz: Google Frontend intercepts that path"
echo "  curl -s \"\$API/readyz\""
