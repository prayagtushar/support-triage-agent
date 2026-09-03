from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent.parent.parent / "evals" / "golden"
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "evals" / "reports"


@dataclass(frozen=True)
class GoldenTicket:
    id: str
    subject: str
    body: str
    expected_intent: str
    expected_urgency: str
    language: str
    expected_route: str
    notes: str


def reports_for(domain_id: str = "ecom") -> list[Path]:
    """Every eval report for one desk, oldest first.

    Picking the newest report without asking which desk it belongs to put a tech run into
    the README's e-commerce metrics block and gated one desk against another's baseline.
    The desk has to be part of the question. Reports written before desks existed carry
    no domain field and were all e-commerce, which is what they are treated as.
    """
    out: list[Path] = []
    for path in sorted(REPORTS_DIR.glob("report_*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if report.get("domain", "ecom") == domain_id:
            out.append(path)
    return out


def latest_report_for(domain_id: str = "ecom") -> Path | None:
    found = reports_for(domain_id)
    return found[-1] if found else None


def load_golden(version: str = "v0") -> list[GoldenTicket]:
    path = GOLDEN_DIR / f"golden_{version}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenTicket(**json.loads(line)) for line in lines if line.strip()]
