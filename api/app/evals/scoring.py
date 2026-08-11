"""Pipeline rows into risk numbers. Accuracy hides the asymmetry; precision and recall show it."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from typing import Any

NEEDS_HUMAN = {"human_review", "escalate"}


def _pairs(rows: Sequence[dict[str, Any]], expected: str, actual: str) -> list[tuple[str, str]]:
    return [
        (str(r[expected]), str(r[actual]))
        for r in rows
        if r.get(expected) is not None and r.get(actual) is not None
    ]


def auto_reply_precision(rows: Sequence[dict[str, Any]]) -> tuple[float, int, int]:
    """Of the tickets we chose to answer without a human, how many should we have?"""
    sent = [r for r in rows if r.get("route") == "auto_reply"]
    correct = [r for r in sent if r.get("expected_route") == "auto_reply"]
    return (len(correct) / len(sent) if sent else 0.0, len(correct), len(sent))


def review_recall(rows: Sequence[dict[str, Any]]) -> tuple[float, int, int]:
    """Of the tickets that needed a human, how many actually got one?"""
    needed = [r for r in rows if r.get("expected_route") in NEEDS_HUMAN]
    caught = [r for r in needed if r.get("route") in NEEDS_HUMAN]
    return (len(caught) / len(needed) if needed else 0.0, len(caught), len(needed))


def accuracy_of(rows: Sequence[dict[str, Any]], expected: str, actual: str) -> float:
    pairs = _pairs(rows, expected, actual)
    if not pairs:
        return 0.0
    return sum(1 for e, a in pairs if e == a) / len(pairs)


def latency_summary(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    totals = sorted(float(r.get("total_ms") or 0) for r in rows if r.get("total_ms"))
    if not totals:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    index = min(len(totals) - 1, round(0.95 * (len(totals) - 1)))
    return {
        "mean_ms": round(statistics.fmean(totals), 1),
        "p50_ms": round(statistics.median(totals), 1),
        "p95_ms": round(totals[index], 1),
    }


def calibration_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": r["id"],
            "composite_confidence": r.get("composite_confidence"),
            "route": r.get("route"),
            "expected_route": r.get("expected_route"),
            "route_correct": int(r.get("route") == r.get("expected_route")),
            "language": r.get("language"),
        }
        for r in rows
        if r.get("composite_confidence") is not None
    ]


def reliability_buckets(rows: Sequence[dict[str, Any]], width: float = 0.1) -> list[dict[str, Any]]:
    """Stated confidence against observed correctness, per bucket."""
    buckets: dict[int, list[dict[str, Any]]] = {}
    for r in calibration_rows(rows):
        confidence = float(r["composite_confidence"])
        index = min(int(confidence / width), round(1 / width) - 1)
        buckets.setdefault(index, []).append(r)

    out = []
    for index in sorted(buckets):
        members = buckets[index]
        out.append(
            {
                "lower": round(index * width, 2),
                "upper": round((index + 1) * width, 2),
                "n": len(members),
                "mean_confidence": round(
                    statistics.fmean(float(m["composite_confidence"]) for m in members), 4
                ),
                "observed_correct": round(
                    sum(int(m["route_correct"]) for m in members) / len(members), 4
                ),
            }
        )
    return out


def sweep_thresholds(
    rows: Sequence[dict[str, Any]], candidates: Sequence[float]
) -> list[dict[str, Any]]:
    """Precision and recall at each threshold, re-routed from recorded signals, not re-run."""
    results = []
    for threshold in candidates:
        rerouted = []
        for r in rows:
            confidence = r.get("composite_confidence")
            hard = r.get("route_reason", "") or ""
            if confidence is None or not hard.startswith("composite"):
                rerouted.append(r)
                continue
            route = "auto_reply" if float(confidence) >= threshold else "human_review"
            rerouted.append({**r, "route": route})

        precision, _, sent = auto_reply_precision(rerouted)
        recall_value, _, needed = review_recall(rerouted)
        results.append(
            {
                "threshold": round(threshold, 3),
                "auto_reply_precision": round(precision, 4),
                "auto_replied": sent,
                "review_recall": round(recall_value, 4),
                "needed_review": needed,
                "routing_accuracy": round(accuracy_of(rerouted, "expected_route", "route"), 4),
            }
        )
    return results
