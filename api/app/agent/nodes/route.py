"""The routing policy: pure Python over model scores. Rules short-circuit, so order matters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings, settings


@dataclass(frozen=True)
class RouteSignals:
    classification: dict[str, Any] | None
    draft: str | None
    judge: dict[str, Any] | None
    retrieval_weak: bool
    retrieval_similarity: float
    is_safe_fallback: bool


def composite_confidence(signals: RouteSignals, config: Settings | None = None) -> float:
    cfg = config or settings
    if signals.judge is None or signals.classification is None:
        return 0.0

    judge_total = (
        int(signals.judge["groundedness"])
        + int(signals.judge["completeness"])
        + int(signals.judge["tone"])
    )
    judge_score = judge_total / 15
    classifier_score = float(signals.classification.get("confidence", 0.0))

    total = (
        cfg.composite_weight_judge * judge_score
        + cfg.composite_weight_classifier * classifier_score
        + cfg.composite_weight_retrieval * signals.retrieval_similarity
    )
    return round(total, 4)


def decide_route(signals: RouteSignals, config: Settings | None = None) -> tuple[str, str]:
    cfg = config or settings

    if signals.classification is None or signals.draft is None or signals.judge is None:
        return "human_review", "pipeline failure upstream, nothing to auto-send"

    urgency = signals.classification.get("urgency")
    if urgency == "P1":
        return "escalate", "P1 never auto-replies regardless of confidence"

    if signals.is_safe_fallback or signals.retrieval_weak:
        return "human_review", "insufficient evidence to answer, drafted a holding reply"

    confidence = composite_confidence(signals, cfg)
    if confidence >= cfg.route_auto_reply_threshold:
        return "auto_reply", f"composite {confidence:.2f} at or above auto-reply threshold"
    if confidence >= cfg.route_review_threshold:
        return "human_review", f"composite {confidence:.2f} in the review band"
    return "escalate", f"composite {confidence:.2f} below the review floor"
