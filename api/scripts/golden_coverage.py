"""Where the golden set is too thin to support the claims made from it.

uv run python scripts/golden_coverage.py [--golden v0] [--resolution 0.05]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from app.corpus import TAXONOMY
from app.evals.golden import REPORTS_DIR, load_golden

# Below this a per-slice rate moves more per ticket than the differences people quote.
THIN = 5

ROUTES = ("auto_reply", "human_review", "escalate")
URGENCIES = ("P1", "P2", "P3", "P4")


def table(title: str, counts: Counter[str], expected: tuple[str, ...] | None = None) -> list[str]:
    keys = list(expected) if expected else sorted(counts)
    width = max(len(k) for k in keys)
    lines = [f"{title}:"]
    for key in keys:
        n = counts.get(key, 0)
        flag = "  <-- thin" if n < THIN else ""
        lines.append(f"  {key:<{width}}  {n:3d}{flag}")
    return lines


def latest_report() -> dict[str, Any] | None:
    reports = sorted(REPORTS_DIR.glob("report_*.json"))
    if not reports:
        return None
    loaded: dict[str, Any] = json.loads(reports[-1].read_text(encoding="utf-8"))
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="v0")
    parser.add_argument(
        "--resolution",
        type=float,
        default=0.05,
        help="how finely auto-reply precision should resolve; 0.05 = one flip moves 5 points",
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    tickets = load_golden(args.golden)
    total = len(tickets)
    print(f"golden {args.golden}: {total} tickets\n")

    intents = Counter(t.expected_intent for t in tickets)
    languages = Counter(t.language for t in tickets)
    urgencies = Counter(t.expected_urgency for t in tickets)
    routes = Counter(t.expected_route for t in tickets)

    for block in (
        table("by intent", intents, TAXONOMY),
        table("by language", languages),
        table("by expected urgency", urgencies, URGENCIES),
        table("by expected route", routes, ROUTES),
    ):
        print("\n".join(block))
        print()

    # Cross-tab: both marginals can look healthy while a quoted cell rests on two tickets.
    print("intent x language, cells below the thin threshold:")
    pairs = Counter((t.expected_intent, t.language) for t in tickets)
    seen_languages = sorted(languages)
    thin_cells = [
        (intent, language, pairs.get((intent, language), 0))
        for intent in TAXONOMY
        for language in seen_languages
        if pairs.get((intent, language), 0) < THIN
    ]
    for intent, language, n in thin_cells:
        print(f"  {intent:<16} {language:<6} {n}")
    print(f"  ({len(thin_cells)} of {len(TAXONOMY) * len(seen_languages)} cells)\n")

    # The denominator problem.
    report = latest_report()
    print("auto-reply precision denominator:")
    if report is None:
        print("  no eval report found; run `make eval` to measure the auto-reply rate\n")
        return 0

    sent = int(report["auto_reply_precision_detail"].split("/")[1])
    measured_on = int(report["tickets"]) - int(report.get("fatal", 0))
    rate = sent / measured_on if measured_on else 0.0
    threshold = report["thresholds"]["auto_reply"]

    print(f"  report {report['label']}, threshold {threshold}")
    print(f"  {sent} of {measured_on} tickets auto-replied -> rate {rate:.3f}")
    if sent:
        print(f"  one flip currently moves precision by {1 / sent:.3f}")

    if rate <= 0:
        print("\n  nothing is auto-replied at this threshold, so precision is undefined.")
        print("  Lower the threshold or grow the set; a rebalance cannot help.\n")
        return 0

    needed_sent = round(1 / args.resolution)
    needed_total = round(needed_sent / rate)
    print(
        f"\n  to resolve precision to +/-{args.resolution:.2f}, the denominator must be "
        f"{needed_sent}, which at this auto-reply rate means ~{needed_total} tickets."
    )
    print(f"  that is {max(0, needed_total - total)} more than the set has now.\n")

    print("what to write, in priority order:")
    priorities: list[str] = []
    if needed_total > total:
        priorities.append(
            f"{needed_total - total} more tickets overall -- this is the only thing that "
            "fixes the headline metric's instability"
        )
    for key, n in sorted(languages.items(), key=lambda kv: kv[1]):
        if n < THIN:
            priorities.append(
                f"{THIN - n} more `{key}` tickets: {n} cannot support a per-language claim"
            )
    for key in ROUTES:
        if routes.get(key, 0) < THIN:
            priorities.append(f"{THIN - routes.get(key, 0)} more expected-`{key}` tickets")
    for key in URGENCIES:
        if urgencies.get(key, 0) < THIN:
            priorities.append(
                f"{THIN - urgencies.get(key, 0)} more `{key}` tickets: the P1-overrides-"
                "everything rule has 17 unit tests and almost no end-to-end coverage"
            )
    for key in TAXONOMY:
        if intents.get(key, 0) < THIN:
            priorities.append(f"{THIN - intents.get(key, 0)} more `{key}` tickets")

    if not priorities:
        print("  nothing thin; the set supports the claims made from it")
    for i, line in enumerate(priorities, 1):
        print(f"  {i}. {line}")
    print()

    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "golden": args.golden,
                    "tickets": total,
                    "by_intent": dict(intents),
                    "by_language": dict(languages),
                    "by_urgency": dict(urgencies),
                    "by_route": dict(routes),
                    "thin_cells": [
                        {"intent": i, "language": lang, "n": n} for i, lang, n in thin_cells
                    ],
                    "auto_reply_rate": round(rate, 4),
                    "target_resolution": args.resolution,
                    "target_tickets": needed_total,
                    "priorities": priorities,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
