"""Policy and health surfaces the dashboard reads. Both public, both cheap.

`/policy` exists so the UI never hardcodes a threshold or a composite weight.
Those live in Settings precisely so a policy change is a config change, and a
dashboard that drew its threshold line from a constant in a TypeScript file
would quietly start lying the first time the config moved.

`/status` is check_degraded.py over HTTP. The failure it watches for is the one
that already happened in production: retrieval returning nothing on every
ticket while every conventional health signal stayed green.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app import repo
from app.config import settings

router = APIRouter(tags=["meta"])


@router.get("/policy")
async def policy() -> dict[str, Any]:
    """The routing policy in force, as numbers the dashboard can draw."""
    return {
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


@router.get("/status")
async def status(last: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Whether recent runs actually worked, not merely whether they finished.

    `degraded` is deliberately computed from the empty-retrieval rate rather
    than from any node's error string. A provider can change its error shape,
    but "retrieval returned nothing" is the symptom that matters to output
    quality however it is worded upstream.
    """
    health = await repo.recent_run_health(last)
    total = int(health["total"])
    if total == 0:
        return {"runs": 0, "degraded": False, "reason": "no runs recorded yet"}

    empty_rate = int(health["empty_retrieval"]) / total
    error_rate = int(health["with_errors"]) / total
    degraded = empty_rate > 0.2

    return {
        "runs": total,
        "degraded": degraded,
        "reason": (
            f"{int(health['empty_retrieval'])} of {total} recent runs retrieved nothing"
            if degraded
            else "retrieval and scoring are producing output"
        ),
        "empty_retrieval_rate": round(empty_rate, 4),
        "error_rate": round(error_rate, 4),
        "routes": health["routes"],
        "tickets_last_24h": await repo.count_tickets_last_24h(),
    }
