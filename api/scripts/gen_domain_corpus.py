"""Generate a resolved-case corpus for a desk that has no real one.

    uv run python scripts/gen_domain_corpus.py --domain tech [--per-topic 8] [--hinglish 60]

Every row is written with source='synthetic'. The e-commerce desk keeps its 3,000 real
Bitext cases and this never touches them. A generated desk is a demonstration that the
architecture is per-domain, not evidence that the system performs on that domain: drafts
there are machine text grounded in machine text, graded by a third machine.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pydantic import BaseModel, Field

from app import repo
from app.agent.domain_topics import DOMAIN_TOPICS
from app.config import settings
from app.db import connect
from app.domains import get as get_domain
from app.errors import TriageError
from app.llm import complete_json

SYSTEM = """You write realistic customer support training data for {context}.

Given one topic, produce distinct support exchanges about it. Each exchange is a
customer message and the reply a good support agent sent.

Rules for the customer message:
- Write the way real customers write: varying length, some terse, some rambling,
  occasional typos, sometimes annoyed. Not all polite and well-formed.
- Vary the specifics across the exchanges: different devices, versions, operating
  systems, timeframes and details. No two should read as rewrites of each other.
- Never use placeholder tokens like {{Ticket Number}}. Write concrete values.
- Do not state the intent label anywhere in the text.

Rules for the resolution:
- What support actually replied: acknowledge, give the concrete steps or the status,
  and say what happens next.
- Plain and warm. No corporate filler.
- For a feature request, the honest reply is thanks, whether it exists today, and that
  it has been logged. Never promise a release date.
- For anything involving a physical device under warranty, the reply may offer an RMA.

Return JSON only."""

HINGLISH_SYSTEM = """You write realistic customer support exchanges in Hinglish for {context}.

Hinglish is romanised Hindi mixed with English, the way Indian customers actually type:
"laptop charge nahi ho raha", "sync bahut slow hai". Devanagari script must not appear.
The support reply is in the same register: warm, plain, mostly English with natural
Hindi words where a real agent would use them.

Vary length and tone. Some terse, some rambling, some annoyed. Return JSON only."""


class Exchange(BaseModel):
    customer_text: str = Field(min_length=20)
    resolution_text: str = Field(min_length=20)


class Batch(BaseModel):
    exchanges: list[Exchange]


async def generate(system: str, user: str) -> list[Exchange]:
    batch, _ = await complete_json(
        provider=settings.classifier_provider,
        model=settings.classifier_model,
        system=system,
        user=user,
        schema=Batch,
        temperature=0.9,
        max_tokens=4096,
    )
    return batch.exchanges


def insert(rows: list[tuple[str, str, str, str, str]]) -> int:
    """(domain_id, intent, language, customer_text, resolution_text)."""
    if not rows:
        return 0
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO resolved_cases
                (domain_id, intent, language, customer_text, resolution_text, source)
            VALUES (%s, %s, %s, %s, %s, 'synthetic')
            """,
            rows,
        )
        conn.commit()
    return len(rows)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    parser.add_argument("--per-topic", type=int, default=8)
    parser.add_argument("--hinglish", type=int, default=60)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--reset", action="store_true", help="delete this desk's cases first")
    args = parser.parse_args()

    if args.domain not in DOMAIN_TOPICS:
        print(f"no topics for {args.domain!r}; known: {list(DOMAIN_TOPICS)}", file=sys.stderr)
        return 2

    await repo.open_pool()
    try:
        domain = await get_domain(args.domain)
    finally:
        await repo.close_pool()

    if not domain.is_synthetic:
        print(
            f"{args.domain} is marked provenance='real'. Generating into it would put "
            "machine text behind claims made about real transcripts.",
            file=sys.stderr,
        )
        return 2

    context, topics = DOMAIN_TOPICS[args.domain]

    if args.reset:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM resolved_cases WHERE domain_id = %s", (args.domain,))
            conn.commit()
            print(f"cleared {cur.rowcount} existing rows")

    unknown = set(topics) - set(domain.intents)
    if unknown:
        print(f"topics name intents this desk does not define: {unknown}", file=sys.stderr)
        return 2

    semaphore = asyncio.Semaphore(args.concurrency)
    system = SYSTEM.format(context=context)

    async def one(intent: str, topic: str) -> list[tuple[str, str, str, str, str]]:
        async with semaphore:
            try:
                exchanges = await generate(
                    system,
                    f'Topic: "{topic}"\nProduce exactly {args.per_topic} distinct exchanges.',
                )
            except TriageError as exc:
                print(f"  {intent:16s} {topic[:40]:40s} FAILED {exc}", file=sys.stderr)
                return []
            print(f"  {intent:16s} {topic[:40]:40s} {len(exchanges):2d}", flush=True)
            return [
                (args.domain, intent, "en", e.customer_text.strip(), e.resolution_text.strip())
                for e in exchanges
            ]

    print(f"generating English cases for {args.domain}")
    batches = await asyncio.gather(
        *(one(intent, topic) for intent, ts in topics.items() for topic in ts)
    )
    rows = [r for b in batches for r in b]
    print(f"inserted {insert(rows)} English cases")

    if args.hinglish:
        print("generating Hinglish cases")
        per_call = 10
        calls = max(1, args.hinglish // per_call)
        intents = list(topics)

        async def hinglish(i: int) -> list[tuple[str, str, str, str, str]]:
            intent = intents[i % len(intents)]
            async with semaphore:
                try:
                    exchanges = await generate(
                        HINGLISH_SYSTEM.format(context=context),
                        f"Intent: {intent}\nProduce exactly {per_call} distinct exchanges.",
                    )
                except TriageError as exc:
                    print(f"  hinglish {intent:14s} FAILED {exc}", file=sys.stderr)
                    return []
                print(f"  hinglish {intent:14s} {len(exchanges):2d}", flush=True)
                return [
                    (
                        args.domain,
                        intent,
                        "hi-en",
                        e.customer_text.strip(),
                        e.resolution_text.strip(),
                    )
                    for e in exchanges
                ]

        hin = await asyncio.gather(*(hinglish(i) for i in range(calls)))
        print(f"inserted {insert([r for b in hin for r in b])} Hinglish cases")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), count(embedding) FROM resolved_cases WHERE domain_id = %s",
            (args.domain,),
        )
        row = cur.fetchone()
    total, embedded = row if row else (0, 0)
    print(f"\n{args.domain}: {total} cases, {embedded} embedded")
    print("run scripts/embed_corpus.py next; retrieval ignores rows with no embedding")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
