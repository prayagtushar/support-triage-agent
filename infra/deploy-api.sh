#!/usr/bin/env bash
# Build and deploy the triage API to Cloud Run.
#
# Assumes gcloud is authenticated, the secrets below exist in Secret Manager,
# and the Artifact Registry repo `triage` exists in asia-south1.
#
# Usage: infra/deploy-api.sh [IMAGE_TAG]      (default tag: latest)

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-triage-agent-prayag}"
REGION="asia-south1"
SERVICE="triage-api"
TAG="${1:-latest}"
IMAGE="asia-south1-docker.pkg.dev/${PROJECT_ID}/triage/api:${TAG}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Building ${IMAGE}..."
gcloud builds submit "${REPO_ROOT}/api" \
  --config "${REPO_ROOT}/infra/cloudbuild.yaml" \
  --substitutions "_IMAGE=${IMAGE}" \
  --project "${PROJECT_ID}"

echo "Deploying to ${SERVICE} (${PROJECT_ID}/${REGION})..."

# --no-cpu-throttling is the flag this whole deployment depends on.
#   POST /tickets returns 202 immediately and runs the 39-48s pipeline in a
#   FastAPI BackgroundTask. With the default throttling, CPU is cut to near zero
#   the moment the response is sent, and the pipeline stalls forever with the
#   ticket stuck at status 'received'. Cloud Run still scales to zero; it just
#   keeps the CPU running while the instance is alive.
#
# --max-instances 1 is correctness, not cost.
#   The provider rate limiters in app/llm/ratelimit.py are per-process and
#   configured to free-tier ceilings. A second instance doubles the real request
#   rate and earns 429s from Gemini and OpenRouter.
#
# 1 vCPU / 512Mi is ample: every node in the pipeline is waiting on a provider
# API, not computing. There are no local models in this image.
#
# --port 8000 because the Dockerfile CMD hardcodes 8000 rather than reading
# $PORT. Cloud Run defaults to expecting 8080 and the container fails its
# startup probe with no useful error. Keeping the port fixed also keeps the
# image identical to what docker-compose runs locally.
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
  --set-env-vars "APP_ENV=prod,LOG_LEVEL=INFO,CORS_ORIGINS=${CORS_ORIGINS:-[\"http://localhost:5173\"]},CLASSIFIER_PROVIDER=openrouter,CLASSIFIER_MODEL=meta-llama/llama-3.3-70b-instruct,DRAFTER_PROVIDER=sarvam,DRAFTER_MODEL=sarvam-105b,JUDGE_PROVIDER=openrouter,JUDGE_MODEL=google/gemini-2.5-flash-lite,EMBEDDING_PROVIDER=gemini,EMBEDDING_MODEL=gemini-embedding-001,EMBEDDING_DIM=1536,ROUTE_AUTO_REPLY_THRESHOLD=0.90,ROUTE_REVIEW_THRESHOLD=0.55,MAX_TICKETS_PER_DAY=50,LANGFUSE_HOST=https://cloud.langfuse.com,LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY:-}" \
  --set-secrets "DATABASE_URL=triage-database-url:latest,SARVAM_API_KEY=triage-sarvam-key:latest,GEMINI_API_KEY=triage-gemini-key:latest,OPENROUTER_API_KEY=triage-openrouter-key:latest,LANGFUSE_SECRET_KEY=triage-langfuse-secret:latest,DEMO_WRITE_KEY=triage-demo-write-key:latest" \
  --ingress all

echo
echo "Deployed. Smoke test:"
echo "  API=\$(gcloud run services describe ${SERVICE} --region ${REGION} --project ${PROJECT_ID} --format 'value(status.url)')"
echo "  curl -s \"\$API/livez\"   # not /healthz: Google Frontend intercepts that path"
echo "  curl -s \"\$API/readyz\""
