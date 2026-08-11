"""Fail if the latest eval report is worse than the blessed baseline.

uv run python scripts/check_regression.py            # check
uv run python scripts/check_regression.py --bless    # adopt the latest report
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

from app.evals.golden import REPORTS_DIR

BASELINE = Path(__file__).resolve().parent.parent / "evals" / "baseline.json"

# One point of tolerance: a gate that fires on sampling noise gets ignored.
TOLERANCE = 0.01

GUARDED = [
    "auto_reply_precision",
    "review_recall",
    "routing_accuracy",
    "intent_accuracy",
]


def latest_report() -> dict[str, Any] | None:
    reports = sorted(glob.glob(str(REPORTS_DIR / "report_*.json")))
    if not reports:
        return None
    with open(reports[-1], encoding="utf-8") as fh:
        return dict(json.load(fh))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bless", action="store_true", help="adopt the latest report as baseline")
    args = parser.parse_args()

    report = latest_report()
    if report is None:
        print("no eval report found; run scripts/run_evals.py first")
        return 1

    if args.bless:
        blessed = {k: report[k] for k in GUARDED}
        blessed["blessed_from"] = report["timestamp"]
        blessed["golden"] = report["golden"]
        blessed["models"] = report["models"]
        blessed["thresholds"] = report["thresholds"]
        BASELINE.write_text(json.dumps(blessed, indent=2), encoding="utf-8")
        print(f"baseline written from {report['timestamp']}")
        for k in GUARDED:
            print(f"  {k:24s} {report[k]:.4f}")
        return 0

    if not BASELINE.exists():
        print("no baseline yet; run with --bless once you are happy with the numbers")
        return 1

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    print(f"comparing {report['timestamp']} against baseline {baseline['blessed_from']}")

    failed = []
    for metric in GUARDED:
        was, now = float(baseline[metric]), float(report[metric])
        delta = now - was
        status = "ok" if delta >= -TOLERANCE else "REGRESSED"
        if status == "REGRESSED":
            failed.append(metric)
        print(f"  {metric:24s} {was:.4f} -> {now:.4f}  {delta:+.4f}  {status}")

    if failed:
        print(f"\n{len(failed)} metric(s) regressed by more than {TOLERANCE}: {failed}")
        return 1
    print("\nno regression")
    return 0


if __name__ == "__main__":
    sys.exit(main())
