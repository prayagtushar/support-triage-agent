"""Fail if the latest eval report for a desk is worse than that desk's baseline.

uv run python scripts/check_regression.py                      # check ecom
uv run python scripts/check_regression.py --domain tech        # check tech
uv run python scripts/check_regression.py --bless              # adopt the latest report

Baselines are per desk. They have to be: the first run after a second desk existed
compared a tech report against an e-commerce baseline and reported three regressions
that were nothing but two different businesses being different.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.evals.golden import latest_report_for

BASELINE = Path(__file__).resolve().parent.parent / "evals" / "baseline.json"

# One point of tolerance: a gate that fires on sampling noise gets ignored.
TOLERANCE = 0.01

GUARDED = [
    "auto_reply_precision",
    "review_recall",
    "routing_accuracy",
    "intent_accuracy",
]


def latest_report(domain_id: str) -> dict[str, Any] | None:
    path = latest_report_for(domain_id)
    return dict(json.loads(path.read_text(encoding="utf-8"))) if path else None


def load_baselines() -> dict[str, Any]:
    """Per-desk baselines, migrating the single-desk file on first read."""
    if not BASELINE.exists():
        return {}
    stored = json.loads(BASELINE.read_text(encoding="utf-8"))
    return stored if "domains" not in stored else dict(stored["domains"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bless", action="store_true", help="adopt the latest report as baseline")
    parser.add_argument("--domain", default="ecom", help="which desk to gate")
    args = parser.parse_args()

    report = latest_report(args.domain)
    if report is None:
        print(f"no eval report found for {args.domain}; run scripts/run_evals.py first")
        return 1

    stored = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {}
    # The old file was one desk's metrics at the top level. Keep it as ecom's.
    baselines = dict(stored.get("domains") or ({"ecom": stored} if stored else {}))

    if args.bless:
        blessed = {k: report[k] for k in GUARDED}
        blessed["blessed_from"] = report["timestamp"]
        blessed["golden"] = report["golden"]
        blessed["models"] = report["models"]
        blessed["thresholds"] = report["thresholds"]
        baselines[args.domain] = blessed
        BASELINE.write_text(json.dumps({"domains": baselines}, indent=2), encoding="utf-8")
        print(f"baseline for {args.domain} written from {report['timestamp']}")
        for k in GUARDED:
            print(f"  {k:24s} {report[k]:.4f}")
        return 0

    baseline = baselines.get(args.domain)
    if baseline is None:
        print(f"no baseline for {args.domain} yet; run with --bless --domain {args.domain}")
        return 1

    print(
        f"{args.domain}: comparing {report['timestamp']} "
        f"against baseline {baseline['blessed_from']}"
    )

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
