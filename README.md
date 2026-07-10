# Support Triage Agent

An LLM agent that triages inbound customer support tickets end to end. Each ticket is classified by intent and urgency, matched against similar resolved cases, answered with a grounded draft reply, scored for confidence, and then routed: high confidence drafts go to an auto-reply queue, everything else lands in a human review queue with full context attached. Every run is traced, and the whole pipeline is measured against a golden dataset that includes Hinglish (code-mixed Hindi and English) tickets.

Ticket triage is one of the most widely deployed production uses of LLM agents because the agent does not need to resolve every ticket. It needs to understand each ticket well enough to classify it, draft a response when the evidence supports one, and know when to hand off to a human. This project treats that handoff as a first-class feature: a deterministic routing policy, a human review queue, and an audit trail, rather than a demo that auto-replies to everything.

## Architecture

```
                       +-----------------------------------------------+
 inbound ticket        |                LangGraph pipeline             |
 POST /tickets  -----> |                                               |
                       |  classify --> retrieve --> draft --> score    |
                       |  (intent,     (similar     (grounded (LLM as  |
                       |   urgency)    resolved      reply,   judge +  |
                       |               cases,        cited)   calib.)  |
                       |               pgvector)                       |
                       |                                 |             |
                       +---------------------------------|-------------+
                                                         v
                                              deterministic router
                                             /          |          \
                                     auto-reply    human review   escalate
                                       queue          queue        queue
                                            \           |         /
                                             +----------+--------+
                                                        |
                                              Next.js dashboard
                                     (queues, drafts, citations, audit log)
```

Key design decisions:

- The agent is a typed state machine (LangGraph), not a free-running loop. Every node has a bounded job, a typed input and output, and its own failure handling, which makes the pipeline testable and its cost predictable.
- Routing is deterministic code over model-produced confidence scores. The LLM proposes; a threshold policy tuned on the eval set disposes.
- Classification runs on a local model (Qwen3 14B via Ollama) because it is a constrained task; drafting runs on Sarvam's hosted models because replies must handle Hinglish natively. Both sit behind one OpenAI-compatible client, so providers are swappable per node.
- Human review is part of the product. Reviewer actions (approve, edit, reject) are stored and become labeled data for the eval suite.

## Stack

| Layer | Choice |
|---|---|
| Agent orchestration | LangGraph (Python) |
| API | FastAPI, Pydantic v2 |
| Models | Sarvam (drafting), Qwen3 14B via Ollama (classification), one OpenAI-compatible client |
| Storage and retrieval | PostgreSQL with pgvector, hybrid vector plus full-text retrieval |
| Observability | Langfuse traces with per-node latency and token cost |
| Evaluation | Golden dataset (including Hinglish tickets), classification F1, routing accuracy, draft groundedness via LLM as judge, confidence calibration |
| Dashboard | Next.js (App Router, TypeScript, Tailwind) |
| Packaging | uv (Python), pnpm (Node), Docker Compose |

## Repository layout

```
api/   FastAPI service and the LangGraph agent (Python, uv)
ui/    Review dashboard (Next.js, pnpm)
```

## Getting started

Prerequisites: Python 3.12+, uv, Node 20+, pnpm, Docker.

API:

```
cd api
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload
# http://localhost:8000/healthz
```

Tests:

```
cd api
uv run pytest
```

Dashboard:

```
cd ui
pnpm install
pnpm dev
# http://localhost:3000
```

## Status

In active development. Build order:

- [x] Repo scaffold: FastAPI service, Next.js dashboard, test setup
- [ ] Data foundation: schema, support ticket corpus, Hinglish golden set
- [ ] Model clients: Sarvam and Ollama behind one interface with cost logging
- [ ] Classifier node with measured baseline
- [ ] Hybrid retrieval over resolved cases
- [ ] Full LangGraph pipeline: draft, confidence, routing
- [ ] API endpoints and run persistence
- [ ] Review dashboard: queues, draft review, audit log
- [ ] Eval suite with regression gate
- [ ] Docker Compose and cloud deployment

## Evaluation

The eval suite runs the full pipeline against a versioned golden dataset and reports classification F1, routing accuracy, draft groundedness, retrieval hit rate, and confidence calibration. Numbers will be published here once the suite is complete; this README will not carry estimates.

## License

MIT. See [LICENSE](LICENSE).
