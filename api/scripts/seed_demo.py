"""Submit a spread of tickets through the real API so every queue has residents.

    uv run python scripts/seed_demo.py [--api http://localhost:8000]

Deterministic demo data is the difference between a demo and a gamble.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from app.evals.golden import GoldenTicket, load_golden

# Chosen to fill all three lanes: easy wins, Hinglish, a P1, a legal threat,
# and one the corpus knows nothing about.
DEMO_IDS = [
    "g021",
    "g003",
    "g031",
    "g038",  # should land in auto-reply
    "g001",
    "g011",
    "g020",  # confident but checkable
    "g006",
    "g026",
    "g041",
    "g042",
    "g046",  # review territory
    "g017",
    "g060",  # P1 overrides
    "g058",  # out of corpus, weak retrieval
]


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args()

    by_id = {t.id: t for t in load_golden()}
    tickets = [by_id[i] for i in DEMO_IDS if i in by_id]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            health = await client.get(f"{args.api}/healthz")
            health.raise_for_status()
        except Exception as exc:
            print(f"API not reachable at {args.api}: {exc}")
            return 1

        semaphore = asyncio.Semaphore(args.concurrency)

        async def submit(t: GoldenTicket) -> None:
            async with semaphore:
                response = await client.post(
                    f"{args.api}/tickets",
                    json={"subject": t.subject, "body": t.body, "channel": "web"},
                )
                status = "ok" if response.status_code == 202 else str(response.status_code)
                print(f"  {t.id}  {status}  {t.subject[:52]}")

        print(f"submitting {len(tickets)} tickets to {args.api}")
        await asyncio.gather(*(submit(t) for t in tickets))

    print("\nsubmitted. The pipeline runs in the background; give it a minute.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
