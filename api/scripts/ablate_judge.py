"""Does the judge actually improve routing, or is it expensive theatre?

uv run python scripts/ablate_judge.py [--report evals/reports/report_x.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.agent.nodes.route import RouteSignals, composite_confidence, decide_route
from app.config import Settings, settings
from app.evals.golden import REPORTS_DIR
from app.evals.scoring import accuracy_of, auto_reply_precision, review_recall

SWEEP = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

# name -> (judge, classifier, retrieval)
ARMS: dict[str, tuple[float, float, float]] = {
    "full": (0.5, 0.3, 0.2),
    "no_judge": (0.0, 0.6, 0.4),
    "judge_only": (1.0, 0.0, 0.0),
}


def latest_report() -> Path:
    reports = sorted(REPORTS_DIR.glob("report_*.json"))
    if not reports:
        raise SystemExit(
            f"no report_*.json in {REPORTS_DIR}. Run `make eval` first, or pass --report."
        )
    return reports[-1]


def signals_of(row: dict[str, Any]) -> RouteSignals:
    """Rebuild the router's inputs from a recorded eval row, and only the keys it reads."""
    return RouteSignals(
        classification={
            "confidence": row.get("classifier_confidence") or 0.0,
            "urgency": row.get("urgency"),
        }
        if row.get("intent") is not None
        else None,
        draft=row.get("draft"),
        judge=row.get("judge_scores"),
        retrieval_weak=bool(row.get("retrieval_weak", True)),
        retrieval_similarity=float(row.get("retrieval_similarity") or 0.0),
        is_safe_fallback=bool(row.get("is_safe_fallback", False)),
    )


def arm_settings(
    weights: tuple[float, float, float], threshold: float, policy: dict[str, Any]
) -> Settings:
    """Settings for one arm, under the policy the report was run with, not current config."""
    judge, classifier, retrieval = weights
    if abs(judge + classifier + retrieval - 1.0) > 1e-6:
        raise SystemExit(f"arm weights must sum to 1.0, got {weights}")
    return settings.model_copy(
        update={
            "composite_weight_judge": judge,
            "composite_weight_classifier": classifier,
            "composite_weight_retrieval": retrieval,
            "route_auto_reply_threshold": threshold,
            "route_review_threshold": policy["review"],
            "weak_retrieval_floor": policy["weak_retrieval_floor"],
        }
    )


def route_all(rows: list[dict[str, Any]], config: Settings) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        signals = signals_of(row)
        route, reason = decide_route(signals, config)
        out.append(
            {
                **row,
                "route": route,
                "route_reason": reason,
                "composite_confidence": composite_confidence(signals, config),
            }
        )
    return out


def measure(rows: list[dict[str, Any]]) -> dict[str, Any]:
    precision, correct, sent = auto_reply_precision(rows)
    recall, caught, needed = review_recall(rows)
    return {
        "auto_reply_precision": round(precision, 4),
        "auto_reply_detail": f"{correct}/{sent}",
        "auto_replied": sent,
        "review_recall": round(recall, 4),
        "review_recall_detail": f"{caught}/{needed}",
        "routing_accuracy": round(accuracy_of(rows, "expected_route", "route"), 4),
    }


def check_fidelity(rows: list[dict[str, Any]], policy: dict[str, Any]) -> tuple[int, list[str]]:
    """The `full` arm must reproduce recorded routes, or signals_of() is wrong."""
    config = arm_settings(ARMS["full"], policy["auto_reply"], policy)
    replayed = route_all(rows, config)
    mismatches = [
        f"{original['id']}: recorded {original.get('route')} != replayed {new['route']}"
        for original, new in zip(rows, replayed, strict=True)
        if original.get("route") != new["route"]
    ]
    return len(replayed), mismatches


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, help="defaults to the newest report in reports/")
    parser.add_argument("--out", type=Path, help="where to write the JSON artifact")
    args = parser.parse_args()

    path = args.report or latest_report()
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = [r for r in report.get("rows", []) if not r.get("fatal")]
    if not rows:
        raise SystemExit(f"{path} has no usable rows")

    policy = report["thresholds"]
    print(
        f"report {path.name}: {len(rows)} usable tickets, "
        f"measured at auto-reply threshold {policy['auto_reply']}\n"
    )

    total, mismatches = check_fidelity(rows, policy)
    if mismatches:
        print(f"FIDELITY CHECK FAILED: {len(mismatches)}/{total} routes not reproduced")
        for line in mismatches[:10]:
            print(f"  {line}")
        print("\nThe recorded signals do not reproduce the recorded routes, so the")
        print("ablation below would be measuring a reconstruction bug. Fix signals_of().")
        return 1
    print(f"fidelity check: {total}/{total} recorded routes reproduced from stored signals\n")

    # Hard rules fire before the composite, so this is the population any arm could move.
    shipped = route_all(rows, arm_settings(ARMS["full"], policy["auto_reply"], policy))
    composite_decided = sum(1 for r in shipped if r["route_reason"].startswith("composite"))
    print(
        f"{composite_decided}/{len(rows)} tickets are decided by the composite; "
        f"the other {len(rows) - composite_decided} are settled by hard rules\n"
        "in every arm, so they cannot distinguish the arms at all.\n"
    )

    results: dict[str, Any] = {
        "report": path.name,
        "measured_at_threshold": policy["auto_reply"],
        "tickets": len(rows),
        "composite_decided": composite_decided,
        "arms": {},
    }

    for name, weights in ARMS.items():
        sweep = []
        for threshold in SWEEP:
            config = arm_settings(weights, threshold, policy)
            sweep.append({"threshold": threshold, **measure(route_all(rows, config))})
        results["arms"][name] = {
            "weights": {"judge": weights[0], "classifier": weights[1], "retrieval": weights[2]},
            "at_report_threshold": next(
                (s for s in sweep if s["threshold"] == policy["auto_reply"]), None
            ),
            "sweep": sweep,
        }

        print(f"=== {name}  (judge {weights[0]}, classifier {weights[1]}, retrieval {weights[2]})")
        print(f"    {'thr':>5s} {'precision':>10s} {'sent':>5s} {'recall':>7s} {'routing':>8s}")
        for s in sweep:
            print(
                f"    {s['threshold']:5.2f} {s['auto_reply_precision']:10.3f} "
                f"{s['auto_replied']:5d} {s['review_recall']:7.3f} {s['routing_accuracy']:8.3f}"
            )
        print()

    # Precision at zero auto-replies is 0.0 by convention, so arms that send nothing are out.
    print("=== best achievable auto-reply precision, arms that answer at least 5 tickets")
    for name, arm in results["arms"].items():
        answering = [s for s in arm["sweep"] if s["auto_replied"] >= 5]
        if not answering:
            print(f"  {name:11s} never auto-replies to 5+ tickets at any threshold")
            continue
        best = max(answering, key=lambda s: s["auto_reply_precision"])
        print(
            f"  {name:11s} {best['auto_reply_precision']:.3f} at threshold "
            f"{best['threshold']:.2f} ({best['auto_reply_detail']}), "
            f"review recall {best['review_recall']:.3f}"
        )

    out_path = args.out or REPORTS_DIR / f"ablation_judge_{path.stem}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
