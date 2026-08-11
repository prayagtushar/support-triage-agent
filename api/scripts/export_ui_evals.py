"""Export the eval evidence the dashboard renders, without the per-ticket rows.

uv run python scripts/export_ui_evals.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.evals.golden import REPORTS_DIR

UI_DATA = Path(__file__).resolve().parent.parent.parent / "ui" / "src" / "data"

# Keys worth shipping; the rest is per-row detail or derivable from these.
KEEP = (
    "label",
    "timestamp",
    "golden",
    "tickets",
    "fatal",
    "tickets_with_errors",
    "models",
    "thresholds",
    "auto_reply_precision",
    "auto_reply_precision_detail",
    "review_recall",
    "review_recall_detail",
    "routing_accuracy",
    "intent_accuracy",
    "intent_macro_f1",
    "urgency_accuracy",
    "language_accuracy",
    "intent_accuracy_english",
    "intent_accuracy_hinglish",
    "safe_fallback_rate",
    "weak_retrieval_rate",
    "latency",
    "cost_inr_per_ticket",
    "reliability",
    "threshold_sweep",
    "per_intent",
    "elapsed_seconds",
)


def newest(pattern: str) -> Path | None:
    found = sorted(REPORTS_DIR.glob(pattern))
    return found[-1] if found else None


def load(path: Path) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


def main() -> int:
    report_path = newest("report_*.json")
    if report_path is None:
        print(f"no report_*.json in {REPORTS_DIR}; run `make eval` first")
        return 1

    report = load(report_path)
    payload: dict[str, Any] = {
        "source": report_path.name,
        "report": {k: report[k] for k in KEEP if k in report},
        "runs": [],
        "ablation": None,
    }

    # Both runs, so the dashboard shows the spread. The instability is the point.
    for path in sorted(REPORTS_DIR.glob("report_*.json")):
        run = load(path)
        payload["runs"].append(
            {
                "label": run.get("label"),
                "source": path.name,
                "threshold": run.get("thresholds", {}).get("auto_reply"),
                "auto_reply_precision": run.get("auto_reply_precision"),
                "auto_reply_precision_detail": run.get("auto_reply_precision_detail"),
                "review_recall": run.get("review_recall"),
                "routing_accuracy": run.get("routing_accuracy"),
                "intent_accuracy": run.get("intent_accuracy"),
                # The runs used different thresholds; the sweep lines them up at a matched one.
                "sweep": run.get("threshold_sweep", []),
            }
        )

    ablation_path = newest("ablation_judge_*.json")
    if ablation_path is not None:
        ablation = load(ablation_path)
        payload["ablation"] = {
            "source": ablation_path.name,
            "tickets": ablation.get("tickets"),
            "composite_decided": ablation.get("composite_decided"),
            "arms": {
                name: {
                    "weights": arm["weights"],
                    "best": max(
                        (s for s in arm["sweep"] if s["auto_replied"] >= 5),
                        key=lambda s: s["auto_reply_precision"],
                        default=None,
                    ),
                    "sweep": arm["sweep"],
                }
                for name, arm in ablation.get("arms", {}).items()
            },
        }

    UI_DATA.mkdir(parents=True, exist_ok=True)
    out = UI_DATA / "evals.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    size = out.stat().st_size
    print(f"wrote {out.relative_to(UI_DATA.parent.parent.parent)}  ({size / 1024:.1f} KB)")
    print(f"  report   {report_path.name}")
    print(f"  runs     {len(payload['runs'])}")
    print(f"  ablation {ablation_path.name if ablation_path else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
