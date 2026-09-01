"""Policy and health, so the dashboard never hardcodes a threshold or guesses at degradation."""

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


@router.get("/status")
async def status(last: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Whether recent runs worked, not merely finished. Keyed on empty retrieval, not errors."""
    health = await repo.recent_run_health(last)
    total = int(health["total"])
    last_run = await repo.last_run_at()
    if total == 0:
        return {"runs": 0, "degraded": False, "reason": "no runs recorded yet", "last_run_at": None}

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
        "last_run_at": last_run,
        "reject_reasons": await repo.reject_reason_counts(),
    }
