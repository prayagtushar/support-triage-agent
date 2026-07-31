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


def load_golden(version: str = "v0") -> list[GoldenTicket]:
    path = GOLDEN_DIR / f"golden_{version}.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    return [GoldenTicket(**json.loads(line)) for line in lines if line.strip()]
