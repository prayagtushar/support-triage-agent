"""Fill the local queues by running the real pipeline, for demos and screenshots.

uv run python scripts/seed_local.py --reset          # wipe and reseed all 60
uv run python scripts/seed_local.py --limit 10       # add ten more
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from app import repo
from app.agent.graph import build_graph
from app.config import settings
from app.db import connect
from app.evals.golden import GoldenTicket, load_golden

ROUTE_TO_STATUS = {
    "auto_reply": "auto_replied",
    "human_review": "in_review",
    "escalate": "escalated",
}


def reset() -> None:
    """Truncate the demo tables. resolved_cases is left alone; re-embedding it is the real cost."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE review_actions, agent_runs, tickets CASCADE")
        conn.commit()
    print("  cleared tickets, agent_runs, review_actions (corpus untouched)")


async def run_one(graph: Any, ticket: GoldenTicket) -> str | None:
    ticket_id = await repo.insert_ticket(
        subject=ticket.subject,
        body=ticket.body,
        channel="web",
        customer_meta={"seeded_from": ticket.id},
        external_ref=ticket.id,
    )
    try:
        final = await graph.ainvoke(
            {
                "ticket_id": ticket_id,
                "subject": ticket.subject,
                "body": ticket.body,
                "channel": "web",
            },
            config={"configurable": {"thread_id": ticket_id}},
        )
    except Exception as exc:
        # Mirrors process_ticket: a failed run still records why and still reaches a human.
        await repo.insert_run(ticket_id, {"errors": [f"pipeline: {exc}"]}, None)
        await repo.update_ticket_status(ticket_id, "in_review")
        print(f"    {ticket.id} FAILED {type(exc).__name__}")
        return ticket_id

    await repo.insert_run(ticket_id, dict(final), None)
    route = str(final.get("route") or "human_review")
    await repo.update_ticket_status(ticket_id, ROUTE_TO_STATUS.get(route, "in_review"))
    confidence = final.get("composite_confidence")
    print(
        f"    {ticket.id:>5}  {route:<13} "
        f"{'' if confidence is None else f'{float(confidence):.3f}'}"
    )
    return ticket_id


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="v0")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--concurrency", type=int, default=settings.eval_concurrency)
    parser.add_argument("--reset", action="store_true", help="truncate tickets first")
    parser.add_argument("--reviews", type=int, default=6, help="how many to also review")
    args = parser.parse_args()

    tickets = load_golden(args.golden)[: args.limit]
    est = len(tickets) * 0.05
    print(f"seeding {len(tickets)} tickets, concurrency {args.concurrency}, ~Rs {est:.2f}")

    await repo.open_pool()
    try:
        if args.reset:
            reset()

        graph = build_graph()
        semaphore = asyncio.Semaphore(args.concurrency)

        async def guarded(t: GoldenTicket) -> str | None:
            async with semaphore:
                return await run_one(graph, t)

        ids = [i for i in await asyncio.gather(*(guarded(t) for t in tickets)) if i]

        # Review a few, with varied actions: an audit page of pure approvals shows nothing.
        if args.reviews:
            reviewed = 0
            plan = [
                ("approve", "Grounded in the retrieved cases, sending as written."),
                ("edit", "Tightened the wording; the substance was right."),
                ("reject", "Promises a timeline no retrieved case supports."),
            ]
            for i, ticket_id in enumerate(ids):
                if reviewed >= args.reviews:
                    break
                detail = await repo.get_ticket_detail(ticket_id)
                if not detail or not detail.get("run_id"):
                    continue
                action, note = plan[i % len(plan)]
                await repo.insert_review_action(
                    run_id=str(detail["run_id"]),
                    action=action,
                    final_text=str(detail.get("draft") or "") if action == "edit" else None,
                    note=note,
                    reviewer="prayag",
                )
                if action != "reject":
                    await repo.update_ticket_status(ticket_id, "resolved")
                reviewed += 1
            print(f"  recorded {reviewed} review actions")

        health = await repo.recent_run_health(200)
        print(f"\n  routes {health['routes']}")
        print(f"  empty retrieval {health['empty_retrieval']}/{health['total']}")
    finally:
        await repo.close_pool()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
