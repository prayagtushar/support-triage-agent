"""Running the pipeline over the golden set, shared by run_golden and run_evals."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from app.agent.graph import build_graph
from app.evals.golden import GoldenTicket


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
    timings = {t["node"]: t["ms"] for t in final.get("node_timings_ms", [])}

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
        "timings_ms": timings,
        "total_ms": sum(timings.values()),
        "cost_inr": round(sum(float(s.get("estimated_cost_inr") or 0.0) for s in stats), 6),
    }


async def run_over_golden(
    tickets: list[GoldenTicket], concurrency: int, on_done: Any = None
) -> list[dict[str, Any]]:
    graph = build_graph()
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0

    async def guarded(t: GoldenTicket) -> dict[str, Any]:
        nonlocal completed
        async with semaphore:
            row = await run_one(graph, t)
            completed += 1
            if on_done:
                on_done(completed, len(tickets), row)
            return row

    return list(await asyncio.gather(*(guarded(t) for t in tickets)))
