#!/usr/bin/env bash
# Move the deployed corpus onto the provider local uses. Re-embed first, deploy second.
#
#   DATABASE_URL='<supabase session pooler url>' infra/migrate-embeddings.sh
#   DATABASE_URL='...' infra/migrate-embeddings.sh --check     # inspect only

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-triage-agent-prayag}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-triage-api}"

TARGET_PROVIDER="openrouter"
TARGET_MODEL="openai/text-embedding-3-small"
TARGET_DIM="1536"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY=false
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

if [[ -z "${DATABASE_URL:-}" ]]; then
  cat >&2 <<'MSG'
DATABASE_URL is not set.

Use the Supabase *session pooler* URL on port 5432, not the direct host:
  postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres

The direct host is IPv6-only and Cloud Run has no IPv6 egress. Port 6543 is
transaction mode and breaks the LangGraph checkpointer's setup. Both are
covered in docs/DEPLOY.md.
MSG
  exit 1
fi

echo "==> Target: ${TARGET_PROVIDER}/${TARGET_MODEL} at ${TARGET_DIM} dims"
echo "==> Database: ${DATABASE_URL##*@}"
echo

cd "${REPO_ROOT}/api"

echo "==> Current corpus state"
uv run python - <<'PY'
import os
from app.db import connect

with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT count(*), count(embedding) FROM resolved_cases")
    total, embedded = cur.fetchone()
    print(f"    {total} cases, {embedded} embedded")
    cur.execute("SELECT count(*) FROM tickets")
    print(f"    {cur.fetchone()[0]} tickets")
PY
echo

if [[ "${CHECK_ONLY}" == true ]]; then
  echo "==> --check given, stopping before any write."
  exit 0
fi

# Re-embedding costs real requests, so make the operator say yes first.
read -r -p "Re-embed the whole corpus through ${TARGET_PROVIDER}? [y/N] " reply
[[ "${reply}" == "y" || "${reply}" == "Y" ]] || { echo "aborted"; exit 1; }

# Clear first: embed_corpus.py only claims WHERE embedding IS NULL, so stale vectors survive.
echo
echo "==> Step 1/4: clearing the old ${TARGET_DIM}-dim vectors"
uv run python - <<'PY'
from app.db import connect

with connect() as conn, conn.cursor() as cur:
    cur.execute("UPDATE resolved_cases SET embedding = NULL WHERE embedding IS NOT NULL")
    print(f"    cleared {cur.rowcount} vectors")
    conn.commit()
PY

echo
echo "==> Step 2/4: re-embedding the corpus (this is the slow part)"
EMBEDDING_PROVIDER="${TARGET_PROVIDER}" \
EMBEDDING_MODEL="${TARGET_MODEL}" \
EMBEDDING_DIM="${TARGET_DIM}" \
  uv run python scripts/embed_corpus.py

echo
echo "==> Step 3/4: verifying every row is embedded before touching the service"
uv run python - <<'PY'
import sys
from app.db import connect

with connect() as conn, conn.cursor() as cur:
    cur.execute("SELECT count(*), count(embedding) FROM resolved_cases")
    total, embedded = cur.fetchone()

print(f"    {embedded}/{total} embedded")
if total == 0 or embedded != total:
    print("    STOP: not every case has a vector. Deploying now would serve")
    print("    queries against a partly re-embedded corpus, which fails quietly.")
    sys.exit(1)
PY

echo
echo "==> Step 4/4: deploy, so the query path uses the same model as the corpus"
cat <<MSG

Not done automatically: this changes a public service, and the corpus write
above is the part that had to happen first.

  1. In infra/deploy-api.sh, set these in --set-env-vars:
         EMBEDDING_PROVIDER=${TARGET_PROVIDER}
         EMBEDDING_MODEL=${TARGET_MODEL}
         EMBEDDING_DIM=${TARGET_DIM}

  2. Deploy:
         infra/deploy-api.sh

  3. Confirm retrieval is actually back -- a 200 is not enough, because the
     broken state also returned 200:

         API=\$(gcloud run services describe ${SERVICE} --region ${REGION} \\
               --project ${PROJECT_ID} --format 'value(status.url)')
         curl -s "\$API/status" | python3 -m json.tool

     Expect "degraded": false and an empty_retrieval_rate near zero. Then
     submit a ticket and check it retrieved cases:

         curl -s "\$API/tickets" | python3 -c \\
           'import json,sys; [print(t["subject"]) for t in json.load(sys.stdin)["tickets"][:3]]'

MSG
