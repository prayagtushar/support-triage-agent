"""SQL over psycopg, parameterised, no ORM. Six tables and a dozen queries worth EXPLAINing."""

from __future__ import annotations

import json
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings

_pool: AsyncConnectionPool | None = None


async def open_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(settings.database_url, min_size=1, max_size=10, open=False)
        await _pool.open(wait=True)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("connection pool is not open; it opens in the app lifespan")
    return _pool


async def _fetch(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    async with get_pool().connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(sql, params or {})
        return list(await cur.fetchall())


async def _fetch_one(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = await _fetch(sql, params)
    return rows[0] if rows else None


async def _execute(sql: str, params: dict[str, Any]) -> None:
    async with get_pool().connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)


async def insert_ticket(
    *,
    subject: str,
    body: str,
    channel: str,
    customer_meta: dict[str, Any],
    external_ref: str | None,
) -> str:
    row = await _fetch_one(
        """
        INSERT INTO tickets (subject, body, channel, customer_meta, external_ref)
        VALUES (%(subject)s, %(body)s, %(channel)s, %(meta)s, %(ref)s)
        RETURNING id::text
        """,
        {
            "subject": subject,
            "body": body,
            "channel": channel,
            "meta": json.dumps(customer_meta),
            "ref": external_ref,
        },
    )
    assert row is not None
    return str(row["id"])


async def update_ticket_status(ticket_id: str, status: str) -> None:
    await _execute(
        "UPDATE tickets SET status = %(status)s WHERE id = %(id)s::uuid",
        {"id": ticket_id, "status": status},
    )


async def count_tickets_last_24h() -> int:
    """Backs the daily cap. Rolling 24h, so the ceiling cannot be doubled across midnight."""
    row = await _fetch_one(
        "SELECT count(*) AS n FROM tickets WHERE created_at > now() - interval '24 hours'"
    )
    return int(row["n"]) if row else 0


async def ticket_visitor(ticket_id: str) -> str | None:
    """Who sent this ticket, by the id their browser generated. Not an identity, and not
    a rate limit: it decides only whether they may review the reply they were sent."""
    row = await _fetch_one(
        "SELECT customer_meta ->> 'visitor' AS visitor FROM tickets WHERE id = %(id)s::uuid",
        {"id": ticket_id},
    )
    return str(row["visitor"]) if row and row["visitor"] else None


async def last_run_at() -> str | None:
    """Heartbeat. A dashboard that only speaks up when broken looks the same as an abandoned one."""
    row = await _fetch_one("SELECT max(created_at) AS at FROM agent_runs")
    at = row["at"] if row else None
    return at.isoformat() if at else None


async def recent_run_health(last: int) -> dict[str, Any]:
    """Recent-run aggregate for /status. Empty retrieval is counted apart from raised errors."""
    row = await _fetch_one(
        """
        WITH recent AS (
            SELECT errors,
                   coalesce(jsonb_array_length(retrieval -> 'cases'), 0) AS cases,
                   route
            FROM agent_runs
            ORDER BY created_at DESC
            LIMIT %(limit)s
        ),
        totals AS (
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE jsonb_array_length(errors) > 0) AS with_errors,
                   count(*) FILTER (WHERE cases = 0) AS empty_retrieval
            FROM recent
        ),
        route_counts AS (
            SELECT coalesce(jsonb_object_agg(route, n), '{}'::jsonb) AS routes
            FROM (
                SELECT route, count(*) AS n
                FROM recent WHERE route IS NOT NULL GROUP BY route
            ) grouped
        )
        SELECT total, with_errors, empty_retrieval, routes FROM totals, route_counts
        """,
        {"limit": last},
    )
    return dict(row) if row else {"total": 0, "with_errors": 0, "empty_retrieval": 0, "routes": {}}


async def insert_run(ticket_id: str, state: dict[str, Any], trace_id: str | None) -> str:
    timings = {t["node"]: t["ms"] for t in state.get("node_timings_ms", [])}
    tokens = {s["node"]: s for s in state.get("call_stats", [])}

    row = await _fetch_one(
        """
        INSERT INTO agent_runs (
            ticket_id, classification, retrieval, draft, draft_citations,
            judge_scores, composite_confidence, route, route_reason,
            errors, latency_ms, token_usage, langfuse_trace_id
        ) VALUES (
            %(ticket_id)s::uuid, %(classification)s, %(retrieval)s, %(draft)s, %(citations)s,
            %(judge)s, %(confidence)s, %(route)s, %(reason)s,
            %(errors)s, %(latency)s, %(tokens)s, %(trace)s
        )
        RETURNING id::text
        """,
        {
            "ticket_id": ticket_id,
            "classification": json.dumps(state.get("classification")),
            "retrieval": json.dumps(
                {
                    "cases": state.get("retrieved_cases", []),
                    "weak": state.get("retrieval_weak"),
                    "best_similarity": state.get("retrieval_similarity"),
                }
            ),
            "draft": state.get("draft"),
            "citations": json.dumps(state.get("draft_citations", [])),
            "judge": json.dumps(state.get("judge_scores")),
            "confidence": state.get("composite_confidence"),
            "route": state.get("route"),
            "reason": state.get("route_reason"),
            "errors": json.dumps(state.get("errors", [])),
            "latency": json.dumps(timings),
            "tokens": json.dumps(tokens),
            "trace": trace_id,
        },
    )
    assert row is not None
    return str(row["id"])


async def list_tickets_by_status(
    status: str | None, limit: int, offset: int
) -> list[dict[str, Any]]:
    return await _fetch(
        """
        SELECT t.id::text, t.subject, t.status, t.channel, t.created_at,
               r.id::text AS run_id, r.route, r.composite_confidence,
               r.classification->>'intent'   AS intent,
               r.classification->>'urgency'  AS urgency,
               r.classification->>'language' AS language
        FROM tickets t
        LEFT JOIN LATERAL (
            SELECT * FROM agent_runs a
            WHERE a.ticket_id = t.id ORDER BY a.created_at DESC LIMIT 1
        ) r ON TRUE
        WHERE %(status)s::text IS NULL OR t.status = %(status)s
        ORDER BY t.created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"status": status, "limit": limit, "offset": offset},
    )


async def get_ticket_detail(ticket_id: str) -> dict[str, Any] | None:
    return await _fetch_one(
        """
        SELECT t.id::text, t.subject, t.body, t.channel, t.status, t.customer_meta, t.created_at,
               r.id::text AS run_id, r.classification, r.retrieval, r.draft, r.draft_citations,
               r.judge_scores, r.composite_confidence, r.route, r.route_reason,
               r.errors, r.latency_ms, r.token_usage, r.langfuse_trace_id,
               r.created_at AS run_created_at
        FROM tickets t
        LEFT JOIN LATERAL (
            SELECT * FROM agent_runs a
            WHERE a.ticket_id = t.id ORDER BY a.created_at DESC LIMIT 1
        ) r ON TRUE
        WHERE t.id = %(id)s::uuid
        """,
        {"id": ticket_id},
    )


async def get_run(run_id: str) -> dict[str, Any] | None:
    return await _fetch_one(
        "SELECT *, id::text AS id, ticket_id::text AS ticket_id FROM agent_runs "
        "WHERE id = %(id)s::uuid",
        {"id": run_id},
    )


async def insert_review_action(
    *,
    run_id: str,
    action: str,
    final_text: str | None,
    note: str | None,
    reviewer: str,
    reason: str | None = None,
    original_text: str | None = None,
) -> str:
    row = await _fetch_one(
        """
        INSERT INTO review_actions
            (run_id, action, final_text, note, reviewer, reason, original_text)
        VALUES
            (%(run_id)s::uuid, %(action)s, %(final_text)s, %(note)s, %(reviewer)s,
             %(reason)s, %(original_text)s)
        RETURNING id::text
        """,
        {
            "run_id": run_id,
            "action": action,
            "final_text": final_text,
            "note": note,
            "reviewer": reviewer,
            "reason": reason,
            "original_text": original_text,
        },
    )
    assert row is not None
    return str(row["id"])


async def list_review_actions(limit: int, offset: int) -> list[dict[str, Any]]:
    return await _fetch(
        """
        SELECT ra.id::text, ra.action, ra.reviewer, ra.note, ra.reason, ra.created_at,
               ra.final_text, ra.original_text,
               r.id::text AS run_id, r.route, r.composite_confidence,
               t.id::text AS ticket_id, t.subject
        FROM review_actions ra
        JOIN agent_runs r ON r.id = ra.run_id
        JOIN tickets t ON t.id = r.ticket_id
        ORDER BY ra.created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"limit": limit, "offset": offset},
    )


async def reject_reason_counts() -> dict[str, int]:
    """Reject reasons, counted. These are the cheapest new eval labels this project gets."""
    rows = await _fetch(
        """
        SELECT reason, count(*) AS n
        FROM review_actions
        WHERE reason IS NOT NULL
        GROUP BY reason
        ORDER BY n DESC
        """
    )
    return {str(r["reason"]): int(r["n"]) for r in rows}


async def queue_counts() -> dict[str, int]:
    rows = await _fetch("SELECT status, count(*) AS n FROM tickets GROUP BY status")
    return {str(r["status"]): int(r["n"]) for r in rows}
