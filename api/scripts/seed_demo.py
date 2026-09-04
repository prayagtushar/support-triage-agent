"""Submit a spread of tickets through the real API so every queue has residents.

uv run python scripts/seed_demo.py [--api http://localhost:8000] [--domain ecom]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx

from app.evals.golden import GoldenTicket, load_golden

# Chosen to fill all three lanes: easy wins, Hinglish, a P1, and one nobody can answer.
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

# Each desk names its own golden file and its own spread. A desk absent from here has no
# demo queue, which is how the tech desk sat at zero tickets while its corpus was ready.
DESKS: dict[str, tuple[str, list[str]]] = {
    "ecom": ("v0", DEMO_IDS),
    "tech": (
        "tech_v0",
        [
            "t001",  # P1 outage
            "t016",  # security report, should escalate
            "t005",  # account access, the one the router gets wrong
            "t008",  # Hinglish outage
            "t021",  # Hinglish performance
            "t007",  # how-to, answerable
            "t019",  # how-to, answerable
            "t006",  # feature request
            "t024",  # too vague to answer
            "t023",  # not a ticket at all
        ],
    ),
}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--domain", default="ecom", choices=sorted(DESKS))
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--key",
        default=os.environ.get("DEMO_WRITE_KEY", ""),
        help=(
            "Value for X-Demo-Key. Required against any deployment that sets "
            "DEMO_WRITE_KEY, which is every deployment that is reachable from the "
            "internet; defaults to $DEMO_WRITE_KEY so it need not be typed."
        ),
    )
    args = parser.parse_args()

    version, wanted = DESKS[args.domain]
    by_id = {t.id: t for t in load_golden(version)}
    tickets = [by_id[i] for i in wanted if i in by_id]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # /livez, not /healthz: Google Frontend intercepts the latter on Cloud Run.
            health = await client.get(f"{args.api}/livez")
            health.raise_for_status()
        except Exception as exc:
            print(f"API not reachable at {args.api}: {exc}")
            return 1

        semaphore = asyncio.Semaphore(args.concurrency)

        headers = {"X-Demo-Key": args.key} if args.key else {}

        async def submit(t: GoldenTicket) -> None:
            async with semaphore:
                response = await client.post(
                    f"{args.api}/tickets",
                    json={
                        "subject": t.subject,
                        "body": t.body,
                        "channel": "web",
                        # Without this every ticket lands on the default desk, which is
                        # why a second desk could never be seeded.
                        "domain_id": args.domain,
                    },
                    headers=headers,
                )
                status = "ok" if response.status_code == 202 else str(response.status_code)
                print(f"  {t.id}  {status}  {t.subject[:52]}")

        print(f"submitting {len(tickets)} tickets to {args.api} on the {args.domain} desk")
        await asyncio.gather(*(submit(t) for t in tickets))

    print("\nsubmitted. The pipeline runs in the background; give it a minute.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
