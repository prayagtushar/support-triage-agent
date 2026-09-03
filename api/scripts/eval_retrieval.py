"""Measure retrieval over the golden set and tune the weak-retrieval floor.

uv run python scripts/eval_retrieval.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.config import settings
from app.evals.golden import REPORTS_DIR, GoldenTicket, load_golden
from app.retrieval.search import find_similar_cases

# Retrieval quality is measured per desk; this script measures the one with real cases.
DOMAIN_ID = "ecom"

# Tickets the corpus cannot cover: dev API, sales enquiry, empty text, pure Devanagari.
EXPECTED_WEAK = {"g058", "g040", "g056", "g057"}


@dataclass(frozen=True)
class Probe:
    id: str
    language: str
    intent: str
    best_similarity: float
    returned: int
    expected_weak: bool


async def probe(ticket: GoldenTicket) -> Probe:
    result = await find_similar_cases(
        domain=DOMAIN_ID, text=f"{ticket.subject}\n{ticket.body}", intent=ticket.expected_intent
    )
    return Probe(
        id=ticket.id,
        language=ticket.language,
        intent=ticket.expected_intent,
        best_similarity=result.best_similarity,
        returned=len(result.cases),
        expected_weak=ticket.id in EXPECTED_WEAK,
    )


def counts_at(probes: list[Probe], floor: float) -> tuple[list[str], list[str]]:
    false_weak = [p.id for p in probes if not p.expected_weak and p.best_similarity < floor]
    missed = [p.id for p in probes if p.expected_weak and p.best_similarity >= floor]
    return false_weak, missed


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="v0")
    args = parser.parse_args()

    golden = load_golden(args.golden)
    print(f"probing retrieval for {len(golden)} tickets with {settings.embedding_model}")

    semaphore = asyncio.Semaphore(4)

    async def guarded(t: GoldenTicket) -> Probe:
        async with semaphore:
            return await probe(t)

    probes = sorted(
        await asyncio.gather(*(guarded(t) for t in golden)), key=lambda p: p.best_similarity
    )

    negatives = [p.best_similarity for p in probes if p.expected_weak]
    positives = [p.best_similarity for p in probes if not p.expected_weak]
    highest_negative = max(negatives) if negatives else 0.0
    lowest_positive = min(positives) if positives else 0.0

    print()
    print("lowest twelve by best similarity:")
    for p in probes[:12]:
        mark = "NEG" if p.expected_weak else "   "
        print(f"  {p.id} {mark} {p.best_similarity:.3f} {p.language:5s} {p.intent}")

    print()
    print(f"  highest uncovered   {highest_negative:.3f}")
    print(f"  lowest covered      {lowest_positive:.3f}")
    separated = "yes" if highest_negative < lowest_positive else "no, they overlap"
    print(f"  cleanly separated   {separated}")

    print()
    print(f"  {'floor':>6s} {'false weak':>11s} {'missed':>7s}")
    candidates = [0.30, 0.35, 0.38, 0.40, 0.42, 0.45, 0.50]
    for floor in candidates:
        false_weak, missed = counts_at(probes, floor)
        flag = "  <- current" if abs(floor - settings.weak_retrieval_floor) < 1e-9 else ""
        print(f"  {floor:6.2f} {len(false_weak):11d} {len(missed):7d}{flag}")

    safe = [f for f in candidates if not counts_at(probes, f)[1]]
    recommended = min(safe) if safe else max(candidates)
    false_weak, missed = counts_at(probes, recommended)
    print()
    print(f"  lowest floor with zero missed: {recommended:.2f}")
    print(f"    false weak there: {len(false_weak)} {false_weak}")

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "golden": args.golden,
        "embedding_model": settings.embedding_model,
        "current_floor": settings.weak_retrieval_floor,
        "recommended_floor": recommended,
        "highest_negative": highest_negative,
        "lowest_positive": lowest_positive,
        "sweep": {
            str(f): {"false_weak": counts_at(probes, f)[0], "missed": counts_at(probes, f)[1]}
            for f in candidates
        },
        "probes": [asdict(p) for p in probes],
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS_DIR / f"retrieval_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreport written to {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
