"""Report tickets whose pipeline never finished.

uv run python scripts/check_stuck.py [--older-than-minutes 5]

This exists because of how the API is deployed. POST /tickets returns 202 and
runs the pipeline in a FastAPI BackgroundTask, after the response is sent. On
Cloud Run that work continues only because the service runs with CPU always
allocated; Google does not contractually guarantee post-response execution, and
scale-down is best-effort.

In practice the idle window is minutes and a run is ~40s, so this should always
report zero. The point is that if the guarantee ever fails, it shows up as a
number here instead of as a customer waiting in a queue nobody looks at.

Exits 1 when anything is stuck, so it can be used as a check.
"""

from __future__ import annotations

import argparse
import sys

from app.config import settings
from app.db import connect

# Beyond this, a run is not slow, it is gone. p95 end-to-end is 39-48s.
DEFAULT_THRESHOLD_MINUTES = 5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--older-than-minutes", type=int, default=DEFAULT_THRESHOLD_MINUTES)
    args = parser.parse_args()

    print(f"checking {settings.database_url.rsplit('@', 1)[-1]}")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, subject, created_at,
                   round(extract(epoch FROM (now() - created_at)) / 60) AS age_minutes
            FROM tickets
            WHERE status = 'received'
              AND created_at < now() - make_interval(mins => %(mins)s)
            ORDER BY created_at
            """,
            {"mins": args.older_than_minutes},
        )
        stuck = cur.fetchall()

    if not stuck:
        print(f"  no tickets stuck longer than {args.older_than_minutes}m")
        return 0

    print(f"  {len(stuck)} ticket(s) stuck in 'received':")
    for ticket_id, subject, _created, age in stuck:
        print(f"    {ticket_id}  {int(age)}m  {subject[:60]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
