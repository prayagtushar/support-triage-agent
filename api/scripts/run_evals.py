"""The eval suite. Runs the pipeline over the golden set and writes three artifacts.

uv run python scripts/run_evals.py [--label v1] [--golden v0]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import UTC, datetime
from typing import Any

from app import repo
from app.config import settings
from app.domains import get as get_domain
from app.evals.golden import REPORTS_DIR, load_golden
from app.evals.metrics import macro_f1, per_label_scores
from app.evals.runner import run_over_golden
from app.evals.scoring import (
    accuracy_of,
    auto_reply_precision,
    calibration_rows,
    latency_summary,
    reliability_buckets,
    review_recall,
    sweep_thresholds,
)

SWEEP = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]


def build_report(
    rows: list[dict[str, Any]],
    label: str,
    golden: str,
    elapsed: float,
    taxonomy: tuple[str, ...],
    domain_id: str,
) -> dict[str, Any]:
    usable = [r for r in rows if not r.get("fatal")]
    precision, precision_correct, precision_sent = auto_reply_precision(usable)
    recall, recall_caught, recall_needed = review_recall(usable)

    intent_pairs = [
        (str(r["expected_intent"]), str(r["intent"])) for r in usable if r.get("intent")
    ]
    # The taxonomy is the desk's, not a constant: scoring a tech run against a
    # shop's eight intents would report perfect recall on labels that cannot occur.
    scores = per_label_scores(intent_pairs, list(taxonomy))

    return {
        "label": label,
        "timestamp": datetime.now(UTC).isoformat(),
        "golden": golden,
        "domain": domain_id,
        "elapsed_seconds": round(elapsed, 1),
        "tickets": len(rows),
        "fatal": len(rows) - len(usable),
        "tickets_with_errors": sum(1 for r in usable if r.get("errors")),
        "models": {
            "classifier": f"{settings.classifier_provider}/{settings.classifier_model}",
            "drafter": f"{settings.drafter_provider}/{settings.drafter_model}",
            "judge": f"{settings.judge_provider}/{settings.judge_model}",
            "embedding": f"{settings.embedding_provider}/{settings.embedding_model}",
        },
        # The label is typed by hand and the settings come from .env, which overrides the
        # defaults in config.py. A run once carried a label naming a token budget it had
        # not used. Record what was actually in force so the two cannot disagree quietly.
        "budgets": {
            "classifier_max_tokens": settings.classifier_max_tokens,
            "drafter_max_tokens": settings.drafter_max_tokens,
            "judge_max_tokens": settings.judge_max_tokens,
        },
        "thresholds": {
            "auto_reply": settings.route_auto_reply_threshold,
            "review": settings.route_review_threshold,
            "weak_retrieval_floor": settings.weak_retrieval_floor,
        },
        "auto_reply_precision": round(precision, 4),
        "auto_reply_precision_detail": f"{precision_correct}/{precision_sent}",
        "review_recall": round(recall, 4),
        "review_recall_detail": f"{recall_caught}/{recall_needed}",
        "routing_accuracy": round(accuracy_of(usable, "expected_route", "route"), 4),
        "intent_accuracy": round(accuracy_of(usable, "expected_intent", "intent"), 4),
        "intent_macro_f1": round(macro_f1(scores), 4),
        "urgency_accuracy": round(accuracy_of(usable, "expected_urgency", "urgency"), 4),
        "language_accuracy": round(accuracy_of(usable, "language", "detected_language"), 4),
        "intent_accuracy_english": round(
            accuracy_of([r for r in usable if r["language"] == "en"], "expected_intent", "intent"),
            4,
        ),
        "intent_accuracy_hinglish": round(
            accuracy_of(
                [r for r in usable if r["language"] == "hi-en"], "expected_intent", "intent"
            ),
            4,
        ),
        "safe_fallback_rate": round(
            sum(1 for r in usable if r.get("is_safe_fallback")) / len(usable), 4
        )
        if usable
        else 0.0,
        "weak_retrieval_rate": round(
            sum(1 for r in usable if r.get("retrieval_weak")) / len(usable), 4
        )
        if usable
        else 0.0,
        "latency": latency_summary(usable),
        "cost_inr_total": round(sum(float(r.get("cost_inr") or 0) for r in usable), 4),
        "cost_inr_per_ticket": round(
            sum(float(r.get("cost_inr") or 0) for r in usable) / len(usable), 6
        )
        if usable
        else 0.0,
        "reliability": reliability_buckets(usable),
        "threshold_sweep": sweep_thresholds(usable, SWEEP),
        "per_intent": [
            {
                "intent": s.label,
                "precision": round(s.precision, 3),
                "recall": round(s.recall, 3),
                "f1": round(s.f1, 3),
                "support": s.support,
            }
            for s in scores
        ],
        "rows": rows,
    }


def write_summary(report: dict[str, Any], path: Any) -> None:
    sweep_table = "\n".join(
        f"| {s['threshold']:.2f} | {s['auto_reply_precision']:.3f} | {s['auto_replied']} | "
        f"{s['review_recall']:.3f} | {s['routing_accuracy']:.3f} |"
        for s in report["threshold_sweep"]
    )
    reliability_table = "\n".join(
        f"| {b['lower']:.1f} to {b['upper']:.1f} | {b['n']} | {b['mean_confidence']:.3f} | "
        f"{b['observed_correct']:.3f} |"
        for b in report["reliability"]
    )
    intent_table = "\n".join(
        f"| {p['intent']} | {p['precision']:.2f} | {p['recall']:.2f} "
        f"| {p['f1']:.2f} | {p['support']} |"
        for p in report["per_intent"]
    )

    path.write_text(
        f"""# Eval summary: {report["label"]}

Golden set `{report["golden"]}`, {report["tickets"]} tickets, {report["elapsed_seconds"]}s.

## Risk metrics

These two lead because they encode the asymmetry. A false auto-reply reaches a
customer; a missed review is a silent failure. Routing accuracy alone hides both.

| Metric | Value | Detail |
|---|---|---|
| **Auto-reply precision** | **{report["auto_reply_precision"]:.3f}** | {report["auto_reply_precision_detail"]} |
| **Review recall** | **{report["review_recall"]:.3f}** | {report["review_recall_detail"]} |
| Routing accuracy | {report["routing_accuracy"]:.3f} | |

## Component accuracy

| Metric | Value |
|---|---|
| Intent accuracy | {report["intent_accuracy"]:.3f} |
| Intent macro F1 | {report["intent_macro_f1"]:.3f} |
| Intent, English only | {report["intent_accuracy_english"]:.3f} |
| Intent, Hinglish only | {report["intent_accuracy_hinglish"]:.3f} |
| Urgency accuracy | {report["urgency_accuracy"]:.3f} |
| Language accuracy | {report["language_accuracy"]:.3f} |

| Behaviour | Rate |
|---|---|
| Safe fallback | {report["safe_fallback_rate"]:.3f} |
| Weak retrieval | {report["weak_retrieval_rate"]:.3f} |

## Cost and latency

| Metric | Value |
|---|---|
| Cost per ticket | Rs {report["cost_inr_per_ticket"]:.4f} |
| Mean end-to-end | {report["latency"]["mean_ms"]:.0f} ms |
| p50 | {report["latency"]["p50_ms"]:.0f} ms |
| p95 | {report["latency"]["p95_ms"]:.0f} ms |

## Calibration

Stated confidence against observed correctness. Points below the diagonal at
the high end are overconfidence, which is where it is dangerous.

| Bucket | n | Mean confidence | Observed correct |
|---|---|---|---|
{reliability_table}

## Threshold sweep

Hard rules (P1, weak retrieval, safe fallback) are held fixed; only the
composite band moves.

| Auto-reply threshold | Precision | Auto-replied | Review recall | Routing accuracy |
|---|---|---|---|---|
{sweep_table}

## Per intent

| Intent | Precision | Recall | F1 | n |
|---|---|---|---|---|
{intent_table}

## Configuration

- classifier `{report["models"]["classifier"]}`
- drafter `{report["models"]["drafter"]}`
- judge `{report["models"]["judge"]}`
- embedding `{report["models"]["embedding"]}`
- thresholds: auto-reply {report["thresholds"]["auto_reply"]}, review {report["thresholds"]["review"]}
- weak retrieval floor {report["thresholds"]["weak_retrieval_floor"]}
- tickets with node errors: {report["tickets_with_errors"]}, fatal: {report["fatal"]}
""",
        encoding="utf-8",
    )


async def preflight() -> str | None:
    """One cheap call per configured provider before committing to a 30-minute run.

    A run that loses its drafter at ticket 44 still writes a report, and that report
    looks like a measurement of a model rather than of an unpaid account. Failing in
    ten seconds is better than failing in twenty minutes with an artifact that has to
    be quarantined afterwards.
    """
    from app.errors import ModelOutputTruncated, ProviderUnavailable
    from app.llm import complete_text

    checks = [
        ("classifier", settings.classifier_provider, settings.classifier_model),
        ("drafter", settings.drafter_provider, settings.drafter_model),
        ("judge", settings.judge_provider, settings.judge_model),
    ]
    for role, provider, model in checks:
        try:
            await complete_text(
                provider=provider,
                model=model,
                system="Reply with: ok",
                user="ok",
                max_tokens=8,
            )
        except ModelOutputTruncated:
            # The probe deliberately allows 8 tokens, and a model that reasons before
            # answering spends all of them thinking. Truncation still proves the thing
            # preflight is asking: the provider answered and billed, so it is reachable
            # and paid for. Treating it as a failure grounded every run on this drafter.
            continue
        except ProviderUnavailable as exc:
            return f"{role} ({provider}/{model}) is not answering: {exc}"
        except Exception as exc:  # a bad key raises before any retry policy applies
            return f"{role} ({provider}/{model}) is not usable: {type(exc).__name__}: {exc}"

    # Models answering is not the same as the pipeline running. Every node resolves its
    # desk through the database, and when that failed each of the 60 rows failed the same
    # way and the run still wrote a full report of zeroes.
    try:
        await repo.domain_case_counts()
    except Exception as exc:
        return f"the database is not usable: {type(exc).__name__}: {exc}"
    return None


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="v0")
    parser.add_argument("--label", default="v1")
    parser.add_argument("--concurrency", type=int, default=settings.eval_concurrency)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--domain", default="ecom", help="which desk to evaluate")
    args = parser.parse_args()

    # Every node now resolves its desk through the pool, so the run needs one open. It
    # used to work without: retrieval opened its own sync connection, and nothing else
    # touched repo. Without this all 60 rows fail identically and still write a report.
    await repo.open_pool()
    try:
        return await _run(args)
    finally:
        await repo.close_pool()


async def _run(args: argparse.Namespace) -> int:
    problem = await preflight()
    if problem:
        print(f"preflight failed, not starting: {problem}", file=sys.stderr)
        print("fix that first; a partial run writes a report that looks real.", file=sys.stderr)
        return 3

    domain = await get_domain(args.domain)
    tickets = load_golden(args.golden)[: args.limit]
    print(
        f"evaluating {len(tickets)} tickets on {domain.id} ({domain.provenance} corpus), "
        f"concurrency {args.concurrency}"
    )

    def progress(done: int, total: int, row: dict[str, Any]) -> None:
        mark = "!" if row.get("errors") or row.get("fatal") else " "
        print(f"  {done:3d}/{total} {mark} {row['id']} -> {row.get('route')}", flush=True)

    started = datetime.now(UTC)
    rows = await run_over_golden(tickets, args.concurrency, progress, domain.id)
    elapsed = (datetime.now(UTC) - started).total_seconds()

    report = build_report(rows, args.label, args.golden, elapsed, domain.intents, domain.id)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    (REPORTS_DIR / f"report_{args.label}_{stamp}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_summary(report, REPORTS_DIR / f"summary_{args.label}_{stamp}.md")

    with (REPORTS_DIR / f"calibration_{args.label}_{stamp}.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        calibration = calibration_rows([r for r in rows if not r.get("fatal")])
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "id",
                "composite_confidence",
                "route",
                "expected_route",
                "route_correct",
                "language",
            ],
        )
        writer.writeheader()
        writer.writerows(calibration)

    print()
    print(
        f"  auto-reply precision  {report['auto_reply_precision']:.3f}  ({report['auto_reply_precision_detail']})"
    )
    print(
        f"  review recall         {report['review_recall']:.3f}  ({report['review_recall_detail']})"
    )
    print(f"  routing accuracy      {report['routing_accuracy']:.3f}")
    print(f"  intent accuracy       {report['intent_accuracy']:.3f}")
    print(f"  cost per ticket       Rs {report['cost_inr_per_ticket']:.4f}")
    print(f"  p95 latency           {report['latency']['p95_ms']:.0f} ms")
    print()
    print("  threshold sweep:")
    print(f"    {'thr':>5s} {'precision':>10s} {'sent':>5s} {'recall':>7s} {'routing':>8s}")
    for s in report["threshold_sweep"]:
        print(
            f"    {s['threshold']:5.2f} {s['auto_reply_precision']:10.3f} {s['auto_replied']:5d} "
            f"{s['review_recall']:7.3f} {s['routing_accuracy']:8.3f}"
        )
    print()
    print(f"  artifacts in evals/reports/ with stamp {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
