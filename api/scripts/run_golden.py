"""Run the whole golden set through the pipeline and record what happened.

uv run python scripts/run_golden.py [--label pipeline] [--limit 10]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from app.agent.graph import build_graph
from app.config import settings
from app.evals.golden import REPORTS_DIR, GoldenTicket, load_golden


async def run_one(graph: Any, ticket: GoldenTicket) -> dict[str, Any]:
    thread = str(uuid.uuid4())
    try:
        final = await graph.ainvoke(
            {"ticket_id": thread, "subject": ticket.subject, "body": ticket.body, "channel": "web"},
            config={"configurable": {"thread_id": thread}},
        )
    except Exception as exc:
        return {"id": ticket.id, "fatal": f"{type(exc).__name__}: {exc}"}

    classification = final.get("classification") or {}
    stats = final.get("call_stats", [])
    return {
        "id": ticket.id,
        "language": ticket.language,
        "expected_intent": ticket.expected_intent,
        "expected_urgency": ticket.expected_urgency,
        "expected_route": ticket.expected_route,
        "intent": classification.get("intent"),
        "urgency": classification.get("urgency"),
        "detected_language": classification.get("language"),
        "sentiment": classification.get("sentiment"),
        "classifier_confidence": classification.get("confidence"),
        "retrieval_weak": final.get("retrieval_weak"),
        "retrieval_similarity": final.get("retrieval_similarity"),
        "draft": final.get("draft"),
        "citations": final.get("draft_citations", []),
        "is_safe_fallback": final.get("draft_is_safe_fallback"),
        "judge_scores": final.get("judge_scores"),
        "composite_confidence": final.get("composite_confidence"),
        "route": final.get("route"),
        "route_reason": final.get("route_reason"),
        "errors": final.get("errors", []),
        "timings_ms": final.get("node_timings_ms", []),
        "cost_inr": round(sum(float(s.get("estimated_cost_inr") or 0.0) for s in stats), 6),
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="v0")
    parser.add_argument("--label", default="pipeline")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=settings.eval_concurrency)
    args = parser.parse_args()

    tickets = load_golden(args.golden)[: args.limit]
    graph = build_graph()
    semaphore = asyncio.Semaphore(args.concurrency)
    done = 0

    async def guarded(t: GoldenTicket) -> dict[str, Any]:
        nonlocal done
        async with semaphore:
            row = await run_one(graph, t)
            done += 1
            mark = "!" if row.get("errors") or row.get("fatal") else " "
            print(f"  {done:3d}/{len(tickets)} {mark} {t.id} -> {row.get('route')}", flush=True)
            return row

    print(f"running {len(tickets)} tickets, concurrency {args.concurrency}")
    started = datetime.now(UTC)
    rows = await asyncio.gather(*(guarded(t) for t in tickets))
    elapsed = (datetime.now(UTC) - started).total_seconds()

    agreed = sum(1 for r in rows if r.get("route") == r.get("expected_route"))
    errored = sum(1 for r in rows if r.get("errors") or r.get("fatal"))
    total_cost = round(sum(float(r.get("cost_inr") or 0) for r in rows), 4)

    report = {
        "label": args.label,
        "timestamp": started.isoformat(),
        "golden": args.golden,
        "elapsed_seconds": round(elapsed, 1),
        "tickets": len(rows),
        "route_agreement": round(agreed / len(rows), 4) if rows else 0.0,
        "tickets_with_errors": errored,
        "total_cost_inr": total_cost,
        "models": {
            "classifier": f"{settings.classifier_provider}/{settings.classifier_model}",
            "drafter": f"{settings.drafter_provider}/{settings.drafter_model}",
            "judge": f"{settings.judge_provider}/{settings.judge_model}",
            "embedding": f"{settings.embedding_provider}/{settings.embedding_model}",
        },
        "rows": rows,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS_DIR / f"golden_{args.label}_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"  route agreement    {report['route_agreement']:.3f}  ({agreed}/{len(rows)})")
    print(f"  tickets w/ errors  {errored}")
    print(f"  elapsed            {elapsed:.0f}s")
    print(f"  total cost         Rs {total_cost}")
    print(f"  report             {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
