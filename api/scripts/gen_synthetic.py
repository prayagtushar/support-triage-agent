"""Generate resolved cases for the two intents Bitext does not cover.

    uv run python scripts/gen_synthetic.py [--per-topic 10] [--reset]

Bitext is consumer commerce and contains no bug_report or feature_request
cases, which would leave both intents permanently weak on retrieval.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from app.agent.synthetic_topics import (
    BUG_REPORT_TOPICS,
    FEATURE_REQUEST_TOPICS,
    PRODUCT_CONTEXT,
)
from app.config import settings
from app.db import connect
from app.errors import TriageError
from app.llm import complete_json

SYSTEM = f"""You write realistic customer support training data for {PRODUCT_CONTEXT}.

Given one topic, produce distinct support exchanges about it. Each exchange is
a customer message and the reply a good support agent sent.

Rules for the customer message:
- Write the way real customers write: varying length, some terse, some rambling,
  occasional typos, sometimes annoyed. Not all polite and well-formed.
- Vary the specifics across the exchanges: different devices, order references,
  timeframes, and details. No two should read as rewrites of each other.
- Never use placeholder tokens like {{{{Order Number}}}}. Write concrete values.

Rules for the resolution:
- What support actually replied: acknowledge, give the concrete steps or the
  status, and say what happens next.
- Plain and warm. No corporate filler.
- For a feature request, the honest reply is thanks, whether it exists today,
  and that it has been logged. Do not promise a release date.

Return JSON only."""


class Exchange(BaseModel):
    customer_text: str = Field(min_length=20)
    resolution_text: str = Field(min_length=20)


class Batch(BaseModel):
    exchanges: list[Exchange]


async def generate(intent: str, topic: str, count: int) -> list[tuple[str, str, str]]:
    batch, stats = await complete_json(
        provider=settings.classifier_provider,
        model=settings.classifier_model,
        system=SYSTEM,
        user=f'Topic: "{topic}"\nIntent: {intent}\nProduce exactly {count} distinct exchanges.',
        schema=Batch,
        temperature=0.9,
        max_tokens=4096,
    )
    print(
        f"  {intent:16s} {topic[:44]:44s} {len(batch.exchanges):2d} cases  {stats.latency_ms:5d}ms"
    )
    return [(intent, e.customer_text.strip(), e.resolution_text.strip()) for e in batch.exchanges]


async def generate_all(per_topic: int, concurrency: int) -> list[tuple[str, str, str]]:
    jobs = [("bug_report", t) for t in BUG_REPORT_TOPICS]
    jobs += [("feature_request", t) for t in FEATURE_REQUEST_TOPICS]

    # Groq's free tier binds on tokens per minute, not requests, and these are
    # long responses.
    semaphore = asyncio.Semaphore(concurrency)

    async def run(intent: str, topic: str) -> list[tuple[str, str, str]]:
        async with semaphore:
            try:
                return await generate(intent, topic, per_topic)
            except TriageError as exc:
                print(f"  SKIP {intent}/{topic[:36]}: {exc}")
                return []

    results = await asyncio.gather(*(run(i, t) for i, t in jobs))
    return [row for batch in results for row in batch]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-topic", type=int, default=10)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM resolved_cases "
            "WHERE source = 'synthetic' AND intent IN ('bug_report', 'feature_request')"
        )
        row = cur.fetchone()
        existing = row[0] if row else 0

        if existing and not args.reset:
            print(f"{existing} synthetic rows already present; pass --reset to replace them")
            return 1
        if args.reset and existing:
            cur.execute(
                "DELETE FROM resolved_cases "
                "WHERE source = 'synthetic' AND intent IN ('bug_report', 'feature_request')"
            )
            print(f"deleted {existing} existing synthetic rows")

        rows = await generate_all(args.per_topic, args.concurrency)
        if not rows:
            print("nothing generated")
            return 1

        cur.executemany(
            """
            INSERT INTO resolved_cases (intent, language, customer_text, resolution_text, source)
            VALUES (%s, 'en', %s, %s, 'synthetic')
            """,
            rows,
        )
        conn.commit()

    print(f"inserted {len(rows)} synthetic rows")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
