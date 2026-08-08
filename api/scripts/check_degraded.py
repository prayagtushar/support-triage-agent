"""Report runs that finished but did not work.

    uv run python scripts/check_degraded.py [--last 50] [--max-error-rate 0.2]

check_stuck.py catches the loud failure: a pipeline that never finished, leaving
a ticket at status 'received'. It cannot see the quiet one, and the quiet one is
the one that actually happened.

On 2026-08-06 the deployed Gemini key ran out of prepaid credits. Every
subsequent retrieve node returned HTTP 429, recorded the error into state, and
handed the router an empty case list. The router did exactly the right thing --
`retrieval_weak` is a hard rule, so every ticket went to a human -- and the
tickets completed with status 'in_review'. Nothing was stuck, no request 500'd,
the health endpoint was fine, and the dashboard rendered. The RAG half of the
system was simply gone, and the only visible symptom was that the auto-reply
and escalate lanes stayed empty.

So this checks the things that stay true while the system keeps serving:

  - node errors recorded per run, broken out by node
  - runs that retrieved nothing, which is retrieval being down rather than
    retrieval being unlucky
  - route distribution, because everything collapsing into one lane is what a
    dead hard-rule input looks like from the outside

Exits 1 when a rate is above threshold, so it can run as a scheduled check.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

from app.config import settings
from app.db import connect

# Enough runs to make a rate meaningful without scanning history.
DEFAULT_WINDOW = 50

# Retrieval returning nothing for a single hard query is plausible. Returning
# nothing for a fifth of a window means the leg is broken, not unlucky.
DEFAULT_MAX_ERROR_RATE = 0.2

NODE_ERROR = re.compile(r"^(\w+):")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--last", type=int, default=DEFAULT_WINDOW)
    parser.add_argument("--max-error-rate", type=float, default=DEFAULT_MAX_ERROR_RATE)
    args = parser.parse_args()

    print(f"checking {settings.database_url.rsplit('@', 1)[-1]}, last {args.last} runs")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT errors,
                   coalesce(jsonb_array_length(retrieval -> 'cases'), 0) AS cases,
                   route
            FROM agent_runs
            ORDER BY created_at DESC
            LIMIT %(limit)s
            """,
            {"limit": args.last},
        )
        rows = cur.fetchall()

    if not rows:
        print("  no runs recorded yet")
        return 0

    total = len(rows)
    with_errors = [r for r in rows if r[0]]
    no_cases = [r for r in rows if r[1] == 0]
    routes = Counter(r[2] or "none" for r in rows)

    # Which node is failing matters more than how many failed. "retrieve: 429"
    # on every run is a dead dependency; one "draft: timeout" is a bad minute.
    by_node: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for errors, _cases, _route in with_errors:
        for error in errors:
            match = NODE_ERROR.match(str(error))
            node = match.group(1) if match else "unknown"
            by_node[node] += 1
            examples.setdefault(node, str(error))

    error_rate = len(with_errors) / total
    empty_rate = len(no_cases) / total

    print(f"  runs with node errors   {len(with_errors):3d}/{total}  ({error_rate:.1%})")
    print(f"  runs retrieving nothing {len(no_cases):3d}/{total}  ({empty_rate:.1%})")
    print(f"  routes                  {dict(routes)}")

    if by_node:
        print("\n  errors by node:")
        for node, count in by_node.most_common():
            print(f"    {node:<12} {count:3d}  {examples[node][:100]}")

    failures = []
    if error_rate > args.max_error_rate:
        failures.append(f"node error rate {error_rate:.1%} above {args.max_error_rate:.1%}")
    if empty_rate > args.max_error_rate:
        failures.append(f"empty-retrieval rate {empty_rate:.1%} above {args.max_error_rate:.1%}")

    # A single lane holding everything is the shape of a dead hard-rule input,
    # even when no node reported an error at all.
    if total >= 5 and len(routes) == 1:
        failures.append(f"every run routed to {next(iter(routes))}, which is not a distribution")

    if not failures:
        print("\n  healthy")
        return 0

    print()
    for line in failures:
        print(f"  DEGRADED: {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
