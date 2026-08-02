# Support Triage Agent

An LLM agent that triages inbound customer support tickets end to end. Each ticket is classified by intent and urgency, matched against similar resolved cases, answered with a grounded draft reply, scored by a second model, and then routed by deterministic code: confident, well-grounded drafts go to an auto-reply queue, everything else lands in a human review queue with the full context attached.

Ticket triage is one of the most widely deployed production uses of LLM agents, because the agent does not need to resolve every ticket. It needs to understand each ticket well enough to classify it, draft a response when the evidence supports one, and know when to hand off. This project treats that handoff as the feature: a deterministic routing policy, a human review queue, an audit trail, and an eval suite that measures whether the handoff decision is any good.

![Review screen](assets/review.png)

A real ticket from the review queue. The drafter promised to reverse a double charge and attached a 3–5 day timeline; the judge scored it 2/5 on groundedness because no retrieved case supports either the action or the timeline. The composite fell to 0.78, below the 0.90 auto-reply threshold, so the router sent it to a human with the draft, the judge's reasoning, and the five cases it retrieved all attached.

![Queues](assets/queues.png)

The review queue. The row with no intent and no confidence is a ticket that failed classification — it skipped retrieval and drafting entirely and was routed straight to a human.

## Architecture

```
                       +-----------------------------------------------+
 inbound ticket        |                LangGraph pipeline             |
 POST /tickets  -----> |                                               |
                       |  classify --> retrieve --> draft --> score    |
                       |  (intent,     (hybrid      (grounded, (second |
                       |   urgency,     vector+FTS,  cited)    model   |
                       |   language)    RRF)                   judges) |
                       |      |                          |             |
                       |      +--- classification failed -+             |
                       |           skips to routing       |             |
                       +----------------------------------|------------+
                                                          v
                                              deterministic router
                                             /          |          \
                                     auto-reply    human review   escalate
                                            \           |         /
                                             +----------+--------+
                                                        |
                                              React dashboard
                                     (queues, drafts, citations, audit log)
```

Key design decisions:

- **The agent is a typed state machine, not a free-running loop.** Every node has a bounded job and its own failure handling. No node raises: failures become state, and the router turns them into a human_review route. A ticket that cannot be classified skips retrieval and drafting entirely, because spending drafter tokens on a ticket you could not classify is waste with extra risk.
- **Routing is deterministic code over model-produced scores.** The LLM proposes; a threshold policy disposes. Thresholds live in configuration, so a policy change is a config change. The router is pure and has 17 unit tests covering every early exit, both threshold boundaries, and P1 beating a perfect composite.
- **The judge runs on a different vendor from the drafter,** enforced at startup rather than by convention — `Settings` refuses to boot if they match. A model grading its own output exhibits self-preference bias, and the router consumes that score as truth.
- **Retrieval reports its own weakness.** The weak signal is raw cosine similarity, not the fused score: fusion is relative to whatever came back, so it stays high even when everything returned is irrelevant. Similarity is absolute and can say "nothing here is close."

## Stack

| Layer | Choice |
|---|---|
| Orchestration | LangGraph, Postgres checkpointer |
| API | FastAPI, Pydantic v2, psycopg3 |
| Storage and retrieval | PostgreSQL + pgvector, hybrid vector + full-text with reciprocal rank fusion |
| Models | Llama 3.3 70B (classify), Sarvam-105B (draft), Gemini 2.5 Flash Lite (judge), text-embedding-3-small — all behind one OpenAI-compatible client |
| Observability | Langfuse traces, structlog JSON logs |
| Evaluation | 60-ticket golden set, threshold sweep, reliability diagram, regression gate |
| Dashboard | Vite, React 19, TanStack Query, Tailwind |
| Packaging | uv, bun, Docker Compose |

## Evaluation

Measured on golden v0 (60 hand-written tickets, 27% non-English, 5 adversarial), auto-reply threshold 0.90. Reports are in `api/evals/reports/`.

| Metric | Value |
|---|---|
| Intent accuracy | **0.950** |
| Language accuracy | **1.000** |
| Intent accuracy, English only | 0.950 |
| Intent accuracy, Hinglish only | 0.867 |
| Review recall | 0.786 – 0.821 |
| Auto-reply precision | 0.500 – 0.778 |
| Routing accuracy | 0.417 – 0.600 |
| Cost per ticket | ₹0.05 |
| p95 end-to-end latency | 39 – 48 s |

**Three things this table is saying honestly, which matter more than the numbers themselves:**

**1. Auto-reply precision does not meet the bar this system was designed against.** The target was 0.95. Across the full threshold sweep the system reaches 0.727 at 0.85 and 0.778 at 0.90; at 0.95 it auto-replies to nothing. The threshold was raised from 0.85 to 0.90 to trade coverage for safety, and the bar was not lowered to make the number look met. On this corpus, auto-reply is not safe to enable at the intended standard.

**2. The ranges are ranges because the metric is unstable at this sample size.** Two runs with identical configuration produced auto-reply precision of 0.778 and 0.500. At a 0.90 threshold only ~10 tickets are auto-replied, so one flip moves precision ten points. Intent accuracy, measured across all 60 tickets, was stable to three decimals across both runs. Growing the golden set to 100+ is a precondition for the headline number to mean anything, not polish.

**3. The composite confidence is overconfident in every bucket.**

| Bucket | n | Stated | Observed | Gap |
|---|---|---|---|---|
| 0.5–0.6 | 5 | 0.582 | 0.400 | −0.182 |
| 0.6–0.7 | 9 | 0.657 | 0.444 | −0.212 |
| 0.7–0.8 | 7 | 0.761 | 0.143 | −0.618 |
| 0.8–0.9 | 28 | 0.859 | 0.714 | −0.145 |
| 0.9–1.0 | 11 | 0.919 | 0.818 | −0.100 |

The weights (0.5 judge, 0.3 classifier, 0.2 retrieval) were a guess, and two of the three inputs are optimistic by construction. Fitting them against outcomes is the obvious next step.

The root cause under most of this is the corpus. Bitext's "resolutions" are largely templates — *"please provide your account details and I'll look it up"* — so retrieval finds topically similar cases that contain no answer to ground on. 25 of 60 drafts declared themselves unable to answer while only 5 had weak retrieval, and the drafter was not wrong to.

## What works well

Classification is strong and language-independent: 0.950 intent accuracy and perfect language detection across English, Hinglish and Devanagari. One measured prompt change took intent accuracy from 0.867 to 0.967 on the classifier eval by fixing a single systematic error — the model was treating "phrased as a question" as meaning `how_to`.

The judge earns its place. Three times during development the drafter invented something and the judge caught it precisely: an invented cancellation-link location, a claim to have checked a transaction the agent has no access to, and a refund timeline supported by nothing. Each time the composite fell and the router sent the ticket to a human instead of a customer.

## Data

3,400 resolved cases: 3,000 from the [Bitext customer support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset) mapped from 27 intents onto 8, plus 400 generated. Bitext contains no `bug_report` or `feature_request` cases at all, so those two intents are synthetic; 80 Hinglish cases are also generated, and are marked `source='synthetic'` in the schema. Rows containing Bitext's `{{Order Number}}`-style template placeholders were dropped rather than filled with invented values.

The Hinglish set has not yet been reviewed by a native speaker, so this README does not describe it as hand-verified.

## Data handling

Every ticket body is sent to three third-party model providers. For this project the corpus is public and synthetic, so nothing sensitive leaves the machine. A production deployment handling real tickets would need PII redaction before egress, or a self-hosted model for the classification step. Sarvam is India-based, which matters for data residency under Indian regulation; the other two are not.

## Getting started

```bash
make up          # Postgres with pgvector
make migrate     # schema
cd api && cp .env.example .env   # then fill in the API keys

uv run python scripts/load_corpus.py
uv run python scripts/gen_synthetic.py
uv run python scripts/gen_hinglish.py
uv run python scripts/embed_corpus.py

make api         # http://localhost:8000
make ui          # http://localhost:5173
make seed        # fill the queues
```

Quality gates and evals:

```bash
make check       # ruff, mypy, offline tests (78 tests, under 2s)
make eval        # full pipeline over the golden set, needs API keys
make calibrate   # reliability diagram
make gate        # fail if the latest run regressed against the baseline
```

The default test suite is offline: anything needing a database, a network call, or an API key is behind the `integration` marker, so `make check` runs clean with nothing else started. Full evals are a pre-merge make target rather than part of that suite — they need provider keys and minutes of runtime.

## Repository layout

```
api/    FastAPI service, the LangGraph agent, eval suite (Python, uv)
ui/     Review dashboard (Vite + React, bun)
infra/  Docker Compose
```

## Licence

MIT. See [LICENSE](LICENSE).
