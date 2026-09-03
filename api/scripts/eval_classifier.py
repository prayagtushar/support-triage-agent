"""Measure the classifier against the golden set.

uv run python scripts/eval_classifier.py [--golden v0] [--label baseline]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime

from app import repo
from app.agent.prompts.classify import build_classify_prompt, build_ticket_user_message
from app.agent.schemas import Classification, classification_for
from app.config import settings
from app.corpus import TAXONOMY
from app.domains import Domain
from app.domains import get as get_domain
from app.errors import TriageError
from app.evals.golden import REPORTS_DIR, GoldenTicket, load_golden
from app.evals.metrics import accuracy, confusion_matrix, macro_f1, per_label_scores
from app.llm import complete_json

URGENCIES = ["P1", "P2", "P3", "P4"]
LANGUAGES = ["en", "hi-en", "hi", "unknown"]


async def classify_one(
    ticket: GoldenTicket, provider: str, model: str, domain: Domain
) -> tuple[GoldenTicket, Classification | None, float, str | None]:
    try:
        result, stats = await complete_json(
            provider=provider,  # type: ignore[arg-type]
            model=model,
            system=build_classify_prompt(domain),
            user=build_ticket_user_message(ticket.subject, ticket.body),
            schema=classification_for(domain.intents),
            temperature=settings.classifier_temperature,
            max_tokens=settings.classifier_max_tokens,
        )
    except TriageError as exc:
        return ticket, None, 0.0, str(exc)
    return ticket, result, stats.estimated_cost_inr or 0.0, None


async def run(
    golden: list[GoldenTicket], provider: str, model: str, concurrency: int, domain: Domain
) -> list[tuple[GoldenTicket, Classification | None, float, str | None]]:
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(
        ticket: GoldenTicket,
    ) -> tuple[GoldenTicket, Classification | None, float, str | None]:
        async with semaphore:
            return await classify_one(ticket, provider, model, domain)

    return await asyncio.gather(*(guarded(t) for t in golden))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="v0")
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--provider", default=settings.classifier_provider)
    parser.add_argument("--model", default=settings.classifier_model)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--domain", default="ecom", help="which desk's taxonomy to score against")
    args = parser.parse_args()

    golden = load_golden(args.golden)
    print(f"classifying {len(golden)} tickets with {args.provider}/{args.model} on {args.domain}")

    async def _go() -> list[tuple[GoldenTicket, Classification | None, float, str | None]]:
        # The taxonomy lives in the database now, so scoring needs a connection even
        # though the classifier itself only talks to a model.
        await repo.open_pool()
        try:
            domain = await get_domain(args.domain)
            return await run(golden, args.provider, args.model, args.concurrency, domain)
        finally:
            await repo.close_pool()

    results = asyncio.run(_go())

    intent_pairs: list[tuple[str, str]] = []
    urgency_pairs: list[tuple[str, str]] = []
    language_pairs: list[tuple[str, str]] = []
    failures: list[dict[str, str]] = []
    disagreements: list[dict[str, object]] = []
    total_cost = 0.0

    for ticket, result, cost, error in results:
        total_cost += cost
        if result is None:
            failures.append({"id": ticket.id, "error": error or "unknown"})
            continue
        intent_pairs.append((ticket.expected_intent, result.intent))
        urgency_pairs.append((ticket.expected_urgency, result.urgency))
        language_pairs.append((ticket.language, result.language))
        if result.intent != ticket.expected_intent:
            disagreements.append(
                {
                    "id": ticket.id,
                    "subject": ticket.subject,
                    "expected": ticket.expected_intent,
                    "predicted": result.intent,
                    "confidence": result.confidence,
                    "rationale": result.rationale,
                }
            )

    intent_scores = per_label_scores(intent_pairs, list(TAXONOMY))
    hinglish = [
        (t.language, r.language)
        for t, r, _, _ in results
        if r is not None and t.language == "hi-en"
    ]
    hinglish_intent = [
        (t.expected_intent, r.intent)
        for t, r, _, _ in results
        if r is not None and t.language == "hi-en"
    ]
    english_intent = [
        (t.expected_intent, r.intent)
        for t, r, _, _ in results
        if r is not None and t.language == "en"
    ]

    report = {
        "label": args.label,
        "timestamp": datetime.now(UTC).isoformat(),
        "golden": args.golden,
        "provider": args.provider,
        "model": args.model,
        "tickets": len(golden),
        "hard_failures": len(failures),
        "intent_accuracy": round(accuracy(intent_pairs), 4),
        "intent_macro_f1": round(macro_f1(intent_scores), 4),
        "urgency_accuracy": round(accuracy(urgency_pairs), 4),
        "language_accuracy": round(accuracy(language_pairs), 4),
        "hinglish_language_accuracy": round(accuracy(hinglish), 4) if hinglish else None,
        "intent_accuracy_english": round(accuracy(english_intent), 4) if english_intent else None,
        "intent_accuracy_hinglish": round(accuracy(hinglish_intent), 4)
        if hinglish_intent
        else None,
        "estimated_cost_inr": round(total_cost, 4),
        "per_intent": [
            {
                "intent": s.label,
                "precision": round(s.precision, 3),
                "recall": round(s.recall, 3),
                "f1": round(s.f1, 3),
                "support": s.support,
            }
            for s in intent_scores
        ],
        "disagreements": disagreements,
        "failures": failures,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS_DIR / f"classifier_{args.label}_{stamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"  intent accuracy    {report['intent_accuracy']:.3f}")
    print(f"  intent macro F1    {report['intent_macro_f1']:.3f}")
    print(f"  urgency accuracy   {report['urgency_accuracy']:.3f}")
    print(f"  language accuracy  {report['language_accuracy']:.3f}")
    if report["hinglish_language_accuracy"] is not None:
        print(f"  hinglish language  {report['hinglish_language_accuracy']:.3f}")
    if report["intent_accuracy_english"] is not None:
        print(f"  intent, en only    {report['intent_accuracy_english']:.3f}")
    if report["intent_accuracy_hinglish"] is not None:
        print(f"  intent, hi-en only {report['intent_accuracy_hinglish']:.3f}")
    print(f"  hard failures      {report['hard_failures']}")
    print(f"  estimated cost     Rs {report['estimated_cost_inr']:.4f}")
    print()
    print("per intent:")
    print(f"  {'intent':16s} {'prec':>6s} {'rec':>6s} {'f1':>6s} {'n':>4s}")
    for s in intent_scores:
        print(f"  {s.label:16s} {s.precision:6.2f} {s.recall:6.2f} {s.f1:6.2f} {s.support:4d}")
    print()
    print(confusion_matrix(intent_pairs, list(TAXONOMY)))
    print()
    print(f"{len(disagreements)} intent disagreements:")
    for d in disagreements:
        print(f"  {d['id']} {d['expected']:>15s} -> {d['predicted']:<15s} conf {d['confidence']}")
        print(f"      {d['subject']}")
    print()
    print(f"report written to {path.relative_to(path.parents[2])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
