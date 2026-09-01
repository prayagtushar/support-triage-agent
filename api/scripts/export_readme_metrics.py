"""Rewrite the README's metrics block from the same export the dashboard reads.

uv run python scripts/export_readme_metrics.py

The README and the dashboard had drifted apart once already: the calibration table
in the README came from a run the evals page no longer showed. Generating both from
one file makes that impossible rather than merely discouraged.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
UI_DATA = ROOT / "ui" / "src" / "data" / "evals.json"
README = ROOT / "README.md"

START = "<!-- metrics:start -->"
END = "<!-- metrics:end -->"


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. The normal approximation misbehaves at n≈10, which is
    exactly the denominator auto-reply precision is measured on."""
    if n == 0:
        return (0.0, 1.0)
    p = hits / n
    denominator = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - spread) / denominator), min(1.0, (centre + spread) / denominator))


def interval(detail: str | None) -> str:
    if not detail or "/" not in detail:
        return "—"
    hits, _, n = detail.partition("/")
    lo, hi = wilson(int(hits), int(n))
    return f"{lo:.2f}\u2013{hi:.2f}"  # en dash, matching the README's typography


def render(data: dict[str, Any]) -> str:
    report = data["report"]
    sweep = report["threshold_sweep"]
    threshold = report["thresholds"]["auto_reply"]
    at = next((s for s in sweep if s["threshold"] == threshold), None)
    lines: list[str] = []

    lines.append(
        f"Run `{report['label']}` on golden `{report['golden']}`, "
        f"{report['tickets']} tickets, auto-reply threshold {threshold}, measured "
        f"{report['timestamp'][:10]}. Regenerate this block with `make readme-metrics`."
    )
    lines.append("")

    # The two proportions the design is accountable to, with the denominators that
    # decide how much of each number is real.
    lines.append("**Decisions the routing gets to make.** Small denominators, so intervals:")
    lines.append("")
    lines.append("| Metric | Value | n | 95% CI |")
    lines.append("|---|---|---|---|")
    precision_detail = report["auto_reply_precision_detail"]
    lines.append(
        f"| Auto-reply precision | **{report['auto_reply_precision']:.3f}** | "
        f"{precision_detail} | {interval(precision_detail)} |"
    )
    lines.append(
        f"| Review recall | {report['review_recall']:.3f} | "
        f"{report['review_recall_detail']} | {interval(report['review_recall_detail'])} |"
    )
    lines.append(
        f"| Routing accuracy | {report['routing_accuracy']:.3f} | {report['tickets']} | — |"
    )
    lines.append("")

    lines.append("**Classification, measured across every ticket.** Stable to three decimals:")
    lines.append("")
    lines.append("| Metric | Value | n |")
    lines.append("|---|---|---|")
    lines.append(f"| Intent accuracy | **{report['intent_accuracy']:.3f}** | {report['tickets']} |")
    lines.append(f"| Intent macro F1 | {report['intent_macro_f1']:.3f} | {report['tickets']} |")
    lines.append(f"| Intent, English | {report['intent_accuracy_english']:.3f} | 44 |")
    lines.append(f"| Intent, Hinglish | {report['intent_accuracy_hinglish']:.3f} | 15 |")
    lines.append(f"| Urgency accuracy | {report['urgency_accuracy']:.3f} | {report['tickets']} |")
    lines.append(f"| Language accuracy | {report['language_accuracy']:.3f} | {report['tickets']} |")
    lines.append("")

    latency = report["latency"]
    lines.append(
        f"**Cost and latency.** ₹{report['cost_inr_per_ticket']:.3f} a ticket · "
        f"p50 {latency['p50_ms'] / 1000:.1f}s · p95 {latency['p95_ms'] / 1000:.1f}s · "
        f"mean {latency['mean_ms'] / 1000:.1f}s. Triage is asynchronous, so p95 bounds how "
        "long a ticket waits before a human sees it in the queue, not how long a customer "
        "waits on a page."
    )
    lines.append("")

    # A routing number with nothing to compare it against cannot be read.
    lines.append("**Against the policies it has to beat:**")
    lines.append("")
    lines.append("| Policy | Auto-reply precision | Review recall | Answers sent |")
    lines.append("|---|---|---|---|")
    lines.append("| Every ticket to a human | never answers | 1.000 | 0 |")
    lines.append(
        f"| Shipped composite at {threshold} | {report['auto_reply_precision']:.3f} | "
        f"{report['review_recall']:.3f} | {at['auto_replied'] if at else '—'} |"
    )
    for name, arm in data.get("ablation", {}).get("arms", {}).items():
        if name == "full" or not arm.get("best"):
            continue
        best = arm["best"]
        lines.append(
            f"| {name.replace('_', ' ').capitalize()}, best threshold | "
            f"{best['auto_reply_precision']:.3f} | {best['review_recall']:.3f} | "
            f"{best['auto_replied']} |"
        )
    lines.append("")

    lines.append("**Calibration.** Every bucket claims more than it delivered:")
    lines.append("")
    lines.append("| Bucket | n | Stated | Observed | Gap |")
    lines.append("|---|---|---|---|---|")
    for bucket in report["reliability"]:
        gap = bucket["observed_correct"] - bucket["mean_confidence"]
        signed = f"\u2212{abs(gap):.3f}" if gap < 0 else f"+{gap:.3f}"
        lines.append(
            f"| {bucket['lower']:.1f}\u2013{bucket['upper']:.1f} | {bucket['n']} | "
            f"{bucket['mean_confidence']:.3f} | {bucket['observed_correct']:.3f} | {signed} |"
        )
    lines.append("")

    lines.append("**Per intent:**")
    lines.append("")
    lines.append("| Intent | Precision | Recall | F1 | Support |")
    lines.append("|---|---|---|---|---|")
    for row in report["per_intent"]:
        lines.append(
            f"| {row['intent'].replace('_', ' ')} | {row['precision']:.3f} | "
            f"{row['recall']:.3f} | {row['f1']:.3f} | {row['support']} |"
        )

    return "\n".join(lines)


def main() -> int:
    if not UI_DATA.exists():
        print(f"no export at {UI_DATA}; run `make ui-evals` first", file=sys.stderr)
        return 1

    text = README.read_text()
    if START not in text or END not in text:
        print(f"README is missing the {START} / {END} markers", file=sys.stderr)
        return 1

    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    block = render(json.loads(UI_DATA.read_text()))

    README.write_text(f"{head}{START}\n\n{block}\n\n{END}{tail}")
    print(f"wrote the metrics block to {README.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
