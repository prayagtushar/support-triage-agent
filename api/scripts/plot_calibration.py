"""Reliability diagram from the latest eval report.

uv run python scripts/plot_calibration.py
"""

from __future__ import annotations

import glob
import json
import sys
from typing import Any

from app.evals.golden import REPORTS_DIR

W, H, PAD = 460, 460, 55


def point(value: float, axis: str) -> float:
    span = W - 2 * PAD if axis == "x" else H - 2 * PAD
    return PAD + value * span if axis == "x" else H - PAD - value * span


def render(buckets: list[dict[str, Any]], threshold: float) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="system-ui, sans-serif" font-size="11">',
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<line x1="{PAD}" y1="{H - PAD}" x2="{W - PAD}" y2="{H - PAD}" stroke="#111"/>',
        f'<line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H - PAD}" stroke="#111"/>',
        # Perfect calibration: stated equals observed.
        f'<line x1="{PAD}" y1="{H - PAD}" x2="{W - PAD}" y2="{PAD}" '
        f'stroke="#bbb" stroke-dasharray="4 4"/>',
        f'<text x="{W / 2}" y="{H - 14}" text-anchor="middle">stated confidence</text>',
        f'<text x="16" y="{H / 2}" text-anchor="middle" '
        f'transform="rotate(-90 16 {H / 2})">observed correct</text>',
    ]

    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        x, y = point(tick, "x"), point(tick, "y")
        parts.append(
            f'<text x="{x}" y="{H - PAD + 16}" text-anchor="middle" fill="#555">{tick}</text>'
        )
        parts.append(f'<text x="{PAD - 8}" y="{y + 4}" text-anchor="end" fill="#555">{tick}</text>')

    tx = point(threshold, "x")
    parts.append(
        f'<line x1="{tx}" y1="{PAD}" x2="{tx}" y2="{H - PAD}" '
        f'stroke="#d33" stroke-dasharray="3 3"/>'
    )
    parts.append(f'<text x="{tx + 4}" y="{PAD + 12}" fill="#d33">auto-reply {threshold}</text>')

    path = []
    for b in buckets:
        x, y = point(float(b["mean_confidence"]), "x"), point(float(b["observed_correct"]), "y")
        path.append(f"{x:.1f},{y:.1f}")
        radius = 3 + min(7, int(b["n"]) ** 0.5)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="#2563eb" opacity="0.75"/>'
        )
        parts.append(
            f'<text x="{x + radius + 3:.1f}" y="{y + 3:.1f}" fill="#555">n={b["n"]}</text>'
        )

    if len(path) > 1:
        parts.insert(-1, f'<polyline points="{" ".join(path)}" fill="none" stroke="#2563eb"/>')

    parts.append("</svg>")
    return "\n".join(parts)


def main() -> int:
    reports = sorted(glob.glob(str(REPORTS_DIR / "report_*.json")))
    if not reports:
        print("no eval report found; run scripts/run_evals.py first")
        return 1

    with open(reports[-1], encoding="utf-8") as fh:
        report = json.load(fh)

    buckets = report.get("reliability", [])
    if not buckets:
        print("report has no reliability buckets")
        return 1

    out = REPORTS_DIR / "calibration.svg"
    out.write_text(render(buckets, float(report["thresholds"]["auto_reply"])), encoding="utf-8")

    print(f"  {'bucket':>12s} {'n':>4s} {'stated':>8s} {'observed':>9s}  gap")
    for b in buckets:
        gap = float(b["observed_correct"]) - float(b["mean_confidence"])
        flag = "  overconfident" if gap < -0.1 else ""
        print(
            f"  {b['lower']:.1f} to {b['upper']:.1f} {b['n']:4d} "
            f"{b['mean_confidence']:8.3f} {b['observed_correct']:9.3f}  {gap:+.3f}{flag}"
        )
    print(f"\nwrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
