# Deploying the Support Triage Agent

The deployed system is three pieces: a FastAPI container on Cloud Run, a static
React build on Vercel, and Postgres with pgvector on Supabase.

| Piece | Where | Cost |
|---|---|---|
| API | Cloud Run `triage-api`, `asia-south1`, project `triage-agent-prayag` | ~₹0, inside the free tier |
| Database | Supabase free project `support-triage`, `ap-south-1` | ₹0 |
| Dashboard | Vercel static build | ₹0 |
| Secrets | Secret Manager, 6 secrets | ~₹20/mo |
| Images | Artifact Registry, cleanup policy applied | ~₹0, under the 0.5 GB free tier |

Budget: **₹150/month**, alerting at 50/90/100%, with a kill switch at 100%.

## The constraints that shaped this

Three properties of the code decide the deployment, and changing any of them
means revisiting the config.

**1. `POST /tickets` does its work after responding.** It returns 202 and runs
the 39–48s pipeline in a FastAPI `BackgroundTask` (`app/routers/tickets.py`).
Cloud Run throttles CPU to near zero once a response is sent, which would stall
the pipeline and strand the ticket at status `received` forever. The deployment
runs with **`--no-cpu-throttling`** so the CPU keeps running between requests.

This is the single most important flag in `infra/deploy-api.sh`. Removing it
does not produce an error — it produces tickets that never leave the queue.

Google does not contractually guarantee post-response work completes;
scale-down is best-effort. In practice the idle window is minutes and a run is
~40s, so a just-served instance is not reclaimed mid-run. `scripts/check_stuck.py`
exists so that if this assumption ever breaks, it shows up as a number.

**2. The rate limiters are per-process.** `app/llm/ratelimit.py` paces requests
in memory against free-tier ceilings. Two instances means double the true rate
and 429s from the providers. **`--max-instances 1` is correctness, not a cost
setting.**

**3. `Settings` refuses to boot if the drafter and judge share a provider.** A
model grading its own output exhibits self-preference bias, and the router
consumes that score as truth. Keep `DRAFTER_PROVIDER=sarvam` and
`JUDGE_PROVIDER=openrouter` split, or the container crash-loops on startup.

## Database

Supabase project `support-triage` in `ap-south-1`, the same region as Cloud Run.

**Use the session pooler, not the direct connection.** The direct host
`db.<ref>.supabase.co` resolves to **IPv6 only** — it has no A record — and
Cloud Run has no IPv6 egress, so the API cannot reach it. The working host is:

```
postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

Port **5432** is session mode, which supports the DDL and prepared statements
that the LangGraph Postgres checkpointer needs at startup. Port 6543 is
transaction mode and will break `checkpointer.setup()`.

Schema and corpus, run locally against that URL:

```bash
cd api
export DATABASE_URL="postgresql://postgres.<ref>:<pw>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
uv run python scripts/migrate.py
uv run python scripts/load_corpus.py     # 3000 Bitext rows
uv run python scripts/gen_synthetic.py   # ~400 LLM calls, ~20 min at free-tier RPM
uv run python scripts/gen_hinglish.py
uv run python scripts/embed_corpus.py    # gemini-embedding-001, 1536-dim
```

Free Supabase projects **pause after ~7 days idle**. A Cloud Scheduler job hits
`/readyz` twice weekly to prevent it. It must be `/readyz` and not the liveness
endpoint: liveness deliberately does not touch the database, so it would not
reset the idle counter.

### `/healthz` is unreachable on Cloud Run

**Google Frontend intercepts `/healthz` before it reaches the container.** That
exact path returns Google's own HTML 404 page; every other unrouted path,
`/healthz2` and `/xhealthz` included, returns this app's JSON `{"detail":"Not
Found"}`. The container is fine — the request never arrives.

Liveness is therefore served at **`/livez`**, with `/healthz` kept as an alias
for the in-container Docker `HEALTHCHECK` and any host not behind Google
Frontend. Probe the deployed service on `/livez`. A `/healthz` probe against the
Cloud Run URL can never pass, and its failure looks exactly like a dead
container.

### Embedding quota

Embedding the corpus is the single largest provider spend in a deployment —
one pass over ~3,500 cases — and it runs against the same Gemini key the live
`/tickets` path uses to embed each incoming query. Exhausting it during setup
takes retrieval down for every subsequent request:

```
429 RESOURCE_EXHAUSTED — "Your prepayment credits are depleted."
```

Check the Gemini balance in AI Studio **before** re-embedding, not after. The
failure is not loud: the retrieve node records the 429 into state and the
router sends the ticket to human review, so the system keeps serving and simply
stops grounding anything. `retrieval: 0 cases` alongside a low groundedness
score in `judge_scores` is the signature.

The corpus is embedded at 1536 dimensions. `_embed_openai_compatible` in
`app/llm/embeddings.py` also supports 1536 natively, so OpenAI's
`text-embedding-3-small` is a drop-in alternative provider — but switching
means re-embedding every row, since vectors from different models are not
comparable.

### This already happened, on 2026-08-06

The deployed Gemini key ran out of prepaid credits. Every retrieve node since
has returned HTTP 429, recorded the error into state, and handed the router an
empty case list. Confirmed on both production tickets:

```json
"retrieval": {"weak": true, "cases": [], "best_similarity": 0.0}
"errors": ["retrieve: HTTP 429: ... Your prepayment credits are depleted ..."]
```

**Nothing looked wrong.** `/readyz` was fine, no request 500'd, no ticket was
stuck, the dashboard rendered without a console error, and the router behaved
correctly — `retrieval_weak` is a hard rule, so every ticket went to a human.
The only outward symptom was that the auto-reply and escalate lanes stayed
empty, which reads as "quiet demo" rather than "retrieval is down".

`scripts/check_stuck.py` cannot see this: those tickets finished.
**`scripts/check_degraded.py` (`make degraded`) is the check that can** — it
reports node-error rate, empty-retrieval rate, and route distribution over
recent runs, and exits non-zero when a rate is above threshold.

### Local and production disagree about the embedding provider

Local `.env` has drifted to `openrouter` / `openai/text-embedding-3-small`,
while `infra/deploy-api.sh` still deploys `EMBEDDING_PROVIDER=gemini` and
`EMBEDDING_MODEL=gemini-embedding-001`. Each side is internally consistent —
its corpus and its queries use the same model — so retrieval works locally and
is merely out of credit in production.

**The order of operations in fixing this is load-bearing.** Changing the
deployed `EMBEDDING_*` variables without re-embedding first is worse than the
current outage: query vectors from one model against corpus vectors from
another produce no error at all, just silently meaningless neighbours. A loud
429 is recoverable; quiet nonsense is not.

Two ways out:

1. **Top up the Gemini balance.** Nothing else changes, retrieval resumes on the
   next request, and the divergence above stays. Cheapest, and leaves the single
   shared-key dependency that caused this in place.
2. **Migrate production to the provider local already uses.** Re-embed the
   deployed corpus *first*, then update the env vars, then redeploy:

   ```bash
   export DATABASE_URL="<supabase session pooler URL>"
   export EMBEDDING_PROVIDER=openrouter
   export EMBEDDING_MODEL=openai/text-embedding-3-small
   uv run python scripts/embed_corpus.py        # ~3,472 rows
   # only after that completes, update the --set-env-vars in deploy-api.sh
   infra/deploy-api.sh
   ```

   This also removes the coupling that caused the outage: embedding the corpus
   and serving live queries no longer share a quota with a hard prepaid ceiling.

## Access model

Reads are public — queues, ticket detail, drafts, judge reasoning, citations
and the audit log — so the project can be evaluated without signing up.

Writes need `X-Demo-Key`:

- `POST /tickets` — spends a pipeline run
- `POST /tickets/{id}/review` — writes to the audit trail

The key lives in Secret Manager as `triage-demo-write-key` and is entered in
the dashboard header, which stores it in `localStorage`. It is deliberately
**not** baked into the Vercel build: a key compiled into a static SPA is
readable by anyone who opens devtools.

Treat the key as a speed bump, not authentication. The real ceiling is
`MAX_TICKETS_PER_DAY` (50, rolling 24h), enforced server-side and applied
whether or not a key is configured — a cap that only bound authenticated
callers would bound nothing, since the key is meant to be handed out.

An empty `DEMO_WRITE_KEY` disables the gate. That is the local-dev default and
what the offline test suite runs against.

## Deploying

```bash
export LANGFUSE_PUBLIC_KEY=pk-lf-...
infra/deploy-api.sh              # builds and deploys, tag defaults to latest
```

`CORS_ORIGINS` no longer needs exporting: the deployed dashboard's origin is the
default in `deploy-api.sh`. It used to be listed here as something to remember,
and on 2026-08-10 a deploy that forgot it narrowed production to a localhost
origin — `--set-env-vars` replaces the whole environment — so every request from
the live dashboard failed preflight. The page still rendered; only its data
disappeared, under "Could not reach the API". Override only for a different
frontend:

```bash
CORS_ORIGINS='["https://example.com"]' infra/deploy-api.sh
```

Dashboard:

```bash
cd ui
VITE_API_URL=https://<cloud-run-url> bun run build
vercel deploy --prod
```

`VITE_API_URL` is baked in at build time, so changing the API URL means a
rebuild, not just an env var change.

## Budget guardrails

A GCP budget **only sends notifications**. The ceiling is enforced by a Cloud
Function in `infra/billing-killswitch/` that subscribes to the budget's Pub/Sub
topic and detaches the billing account at 100%, which stops every billable
service in the project.

Two IAM grants are required, and both failed silently when first configured:

- `roles/run.invoker` on the function, for the Eventarc trigger's service
  account. Without it Pub/Sub cannot invoke the function at all and every
  notification bounces with a 401.
- `roles/browser` on the project, in addition to `roles/billing.projectManager`.
  The latter does not include `resourcemanager.projects.get`, which
  `getBillingInfo` needs, so the function 403s.

Neither failure is visible from the console — the function shows as healthy.
**Test the kill switch after any change to it**, ideally while nothing is
deployed:

```bash
gcloud pubsub topics publish billing-kill-switch --project=triage-agent-prayag \
  --message='{"costAmount":450,"budgetAmount":400}'
# expect billingEnabled to go false, then relink:
gcloud billing projects link triage-agent-prayag --billing-account=<account>
```

support-triage-agent lives in **its own GCP project** so that cost is
attributable per app and this kill switch cannot take down anything else.

Note the budget must be denominated in **INR** — the billing account's
currency. A USD budget is rejected with a bare `INVALID_ARGUMENT`.

## Recovering from a kill-switch trip

```bash
gcloud billing projects link triage-agent-prayag --billing-account=<account>
gcloud run services describe triage-api --region asia-south1 --project triage-agent-prayag
```

Then find out what spent the money before redeploying.

## Verification

```bash
API=$(gcloud run services describe triage-api --region asia-south1 \
      --project triage-agent-prayag --format 'value(status.url)')

curl -s "$API/livez"                         # {"status":"ok"}
curl -s "$API/readyz"                        # {"status":"ready","database":"up"}
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$API/tickets" \
  -H 'Content-Type: application/json' -d '{"subject":"x","body":"y"}'   # 401

# with the key: expect 202, then confirm the pipeline actually ran
curl -s -X POST "$API/tickets" -H "X-Demo-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"subject":"charged twice","body":"I was billed twice this month"}'
sleep 60
curl -s "$API/tickets/<id>" | jq '.status'   # must NOT be "received"
```

That last check is the one that matters. It is the direct test of whether
background work survives on Cloud Run, and it should be repeated after the
service has scaled to zero (~20 min idle) to cover the cold-start path.
