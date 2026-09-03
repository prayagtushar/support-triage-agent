"""Policy and health, so the dashboard never hardcodes a threshold or guesses at degradation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app import domains, repo
from app.config import settings

router = APIRouter(tags=["meta"])

# One empty run is a hard ticket. A fifth of the window is a broken component.
DEGRADED_RATE = 0.2


@router.get("/policy")
async def policy() -> dict[str, Any]:
    """The routing policy in force, as numbers the dashboard can draw."""
    return {
        "domain": settings.domain,
        "thresholds": {
            "auto_reply": settings.route_auto_reply_threshold,
            "review": settings.route_review_threshold,
            "weak_retrieval_floor": settings.weak_retrieval_floor,
        },
        "composite_weights": {
            "judge": settings.composite_weight_judge,
            "classifier": settings.composite_weight_classifier,
            "retrieval": settings.composite_weight_retrieval,
        },
        "models": {
            "classifier": f"{settings.classifier_provider}/{settings.classifier_model}",
            "drafter": f"{settings.drafter_provider}/{settings.drafter_model}",
            "judge": f"{settings.judge_provider}/{settings.judge_model}",
            "embedding": f"{settings.embedding_provider}/{settings.embedding_model}",
        },
        "max_tickets_per_day": settings.max_tickets_per_day,
    }


@router.get("/domains")
async def list_domains() -> dict[str, Any]:
    """Every desk this deployment serves.

    Carries the case counts because a desk with no corpus behaves completely differently
    from a full one and the difference is invisible from the queue screen: retrieval
    returns nothing, every draft is ungrounded, and every ticket is correctly routed to a
    human. Better to say so on the switcher than to let it read as a quiet failure.
    """
    registry = await domains.load()
    counts = await repo.domain_case_counts()
    queues = {q["domain_id"]: q for q in await repo.domain_queue_counts()}

    return {
        "domains": [
            {
                **d.as_dict(),
                "cases": counts.get(d.id, {}).get("cases", 0),
                "embedded": counts.get(d.id, {}).get("embedded", 0),
                "synthetic_cases": counts.get(d.id, {}).get("synthetic", 0),
                "tickets": int(queues.get(d.id, {}).get("tickets", 0)),
                "in_review": int(queues.get(d.id, {}).get("in_review", 0)),
                "auto_replied": int(queues.get(d.id, {}).get("auto_replied", 0)),
                "escalated": int(queues.get(d.id, {}).get("escalated", 0)),
                # A desk with no embedded evidence cannot ground a draft. Say it plainly.
                "ready": counts.get(d.id, {}).get("embedded", 0) > 0,
            }
            for d in registry.values()
        ],
        "default": await domains.default_id(),
    }


@router.get("/status")
async def status(last: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Whether recent runs worked, not merely finished.

    Two ways to serve without working, and they need different words. Retrieval can stop
    returning evidence, which is the outage this endpoint was written for. The drafter can
    also stop returning drafts, which happened when its reasoning outgrew its token budget
    and cost 23 of 60 golden drafts while every conventional signal stayed still.
    """
    health = await repo.recent_run_health(last)
    total = int(health["total"])
    last_run = await repo.last_run_at()
    if total == 0:
        return {"runs": 0, "degraded": False, "reason": "no runs recorded yet", "last_run_at": None}

    empty_retrieval = int(health["empty_retrieval"])
    empty_draft = int(health["empty_draft"])
    empty_rate = empty_retrieval / total
    draft_rate = empty_draft / total
    error_rate = int(health["with_errors"]) / total

    # Retrieval first: a draft written without evidence is downstream of that, so naming
    # the drafter while retrieval is dead would point at the wrong component.
    if empty_rate > DEGRADED_RATE:
        kind: str | None = "retrieval"
        reason = f"{empty_retrieval} of {total} recent runs retrieved nothing"
    elif draft_rate > DEGRADED_RATE:
        kind = "drafting"
        reason = f"{empty_draft} of {total} recent runs produced no draft"
    else:
        kind = None
        reason = "retrieval and drafting are producing output"

    return {
        "runs": total,
        "degraded": kind is not None,
        "degraded_kind": kind,
        "reason": reason,
        "empty_retrieval_rate": round(empty_rate, 4),
        "empty_draft_rate": round(draft_rate, 4),
        "error_rate": round(error_rate, 4),
        "routes": health["routes"],
        "tickets_last_24h": await repo.count_tickets_last_24h(),
        "last_run_at": last_run,
        "reject_reasons": await repo.reject_reason_counts(),
    }
