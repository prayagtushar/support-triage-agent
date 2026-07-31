"""Rewrite English corpus cases as Hinglish.

    uv run python scripts/gen_hinglish.py [--per-intent 10] [--reset]

There is no good public Hinglish support corpus, so these are generated and
marked source='synthetic', language='hi-en'. They are hand-reviewed afterwards;
the failure mode to hunt is translationese, sentences that are grammatically
Hinglish but that no human would type.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from app.config import settings
from app.corpus import TAXONOMY
from app.db import connect
from app.errors import TriageError
from app.llm import complete_json

SYSTEM = """You rewrite an English customer support exchange as natural Hinglish,
the way a real Indian customer and support agent would write.

Rules for the customer message:
- Romanized Hindi mixed with English. Latin script only, no Devanagari.
- Keep product names, technical terms, error codes, and amounts in English.
- Natural code-switching, not word-by-word translation. It should read like a
  real WhatsApp or email message from an Indian user.
- Keep the same problem, the same specifics, and roughly the same length.

Rules for the resolution:
- Polite, helpful Hinglish in the same register, technical terms in English.
- Same resolution content as the original. Do not add new promises.

Return JSON only."""


class Rewrite(BaseModel):
    customer_text: str = Field(min_length=10)
    resolution_text: str = Field(min_length=10)


async def rewrite(intent: str, customer: str, resolution: str) -> tuple[str, str, str] | None:
    try:
        result, _ = await complete_json(
            provider=settings.drafter_provider,
            model=settings.drafter_model,
            system=SYSTEM,
            user=f"ORIGINAL\nCustomer: {customer}\nResolution: {resolution}",
            schema=Rewrite,
            temperature=0.7,
            max_tokens=settings.drafter_max_tokens,
        )
    except TriageError as exc:
        print(f"  SKIP {intent}: {exc}")
        return None
    return (intent, result.customer_text.strip(), result.resolution_text.strip())


def sample_sources(per_intent: int) -> list[tuple[str, str, str]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT intent, customer_text, resolution_text
            FROM (
                SELECT intent, customer_text, resolution_text,
                       row_number() OVER (PARTITION BY intent ORDER BY md5(id::text)) AS rn
                FROM resolved_cases
                WHERE language = 'en' AND intent = ANY(%s)
            ) ranked
            WHERE rn <= %s
            """,
            (list(TAXONOMY), per_intent),
        )
        return [(row[0], row[1], row[2]) for row in cur.fetchall()]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-intent", type=int, default=10)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM resolved_cases WHERE language = 'hi-en'")
        row = cur.fetchone()
        existing = row[0] if row else 0

    if existing and not args.reset:
        print(f"{existing} Hinglish rows already present; pass --reset to replace them")
        return 1

    sources = sample_sources(args.per_intent)
    print(f"rewriting {len(sources)} cases with {settings.drafter_model}")

    semaphore = asyncio.Semaphore(args.concurrency)

    async def run(item: tuple[str, str, str]) -> tuple[str, str, str] | None:
        async with semaphore:
            return await rewrite(*item)

    results = await asyncio.gather(*(run(item) for item in sources))
    rows = [r for r in results if r is not None]

    if not rows:
        print("nothing generated")
        return 1

    with connect() as conn, conn.cursor() as cur:
        if args.reset and existing:
            cur.execute("DELETE FROM resolved_cases WHERE language = 'hi-en'")
            print(f"deleted {existing} existing Hinglish rows")
        cur.executemany(
            """
            INSERT INTO resolved_cases (intent, language, customer_text, resolution_text, source)
            VALUES (%s, 'hi-en', %s, %s, 'synthetic')
            """,
            rows,
        )
        conn.commit()

    print(f"inserted {len(rows)} Hinglish rows ({len(sources) - len(rows)} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
