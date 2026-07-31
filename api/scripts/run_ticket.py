"""Run one ticket through the full pipeline and print the final state.

uv run python scripts/run_ticket.py "subject" "body"
uv run python scripts/run_ticket.py --golden g041
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid

from app.agent.graph import build_graph
from app.evals.golden import load_golden


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("subject", nargs="?")
    parser.add_argument("body", nargs="?")
    parser.add_argument("--golden", help="run a golden ticket by id")
    parser.add_argument("--json", action="store_true", help="dump the raw final state")
    args = parser.parse_args()

    if args.golden:
        ticket = next((t for t in load_golden() if t.id == args.golden), None)
        if ticket is None:
            print(f"no golden ticket {args.golden}")
            return 1
        subject, body = ticket.subject, ticket.body
        print(
            f"golden {ticket.id}: expected {ticket.expected_intent}/{ticket.expected_urgency} "
            f"-> {ticket.expected_route}"
        )
    elif args.subject and args.body:
        subject, body = args.subject, args.body
    else:
        parser.error("give a subject and body, or --golden <id>")

    graph = build_graph()
    ticket_id = str(uuid.uuid4())
    final = await graph.ainvoke(
        {"ticket_id": ticket_id, "subject": subject, "body": body, "channel": "web"},
        config={"configurable": {"thread_id": ticket_id}},
    )

    if args.json:
        print(json.dumps(final, indent=2, ensure_ascii=False, default=str))
        return 0

    classification = final.get("classification") or {}
    print()
    print(
        f"  intent      {classification.get('intent')}  urgency {classification.get('urgency')}"
        f"  language {classification.get('language')}  sentiment {classification.get('sentiment')}"
    )
    print(f"  classifier confidence {classification.get('confidence')}")
    print(
        f"  retrieval   {len(final.get('retrieved_cases', []))} cases, "
        f"best similarity {final.get('retrieval_similarity')}, weak={final.get('retrieval_weak')}"
    )
    print(f"  judge       {final.get('judge_scores')}")
    print(f"  composite   {final.get('composite_confidence')}")
    print(f"  ROUTE       {final.get('route')}  ({final.get('route_reason')})")
    fallback = final.get("draft_is_safe_fallback")
    print(f"  citations   {final.get('draft_citations')}  fallback={fallback}")
    print(f"  timings     {final.get('node_timings_ms')}")
    if final.get("errors"):
        print(f"  errors      {final['errors']}")
    print()
    print("  --- draft ---")
    for line in (final.get("draft") or "(none)").splitlines():
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
