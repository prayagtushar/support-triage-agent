from __future__ import annotations

import uuid
from typing import Any, Literal

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app import repo
from app.agent.checkpoint import get_checkpointer
from app.agent.graph import build_graph
from app.config import settings
from app.observability import flush, trace_run

log = structlog.get_logger()
router = APIRouter(tags=["tickets"])


async def require_write_key(x_demo_key: str | None = Header(default=None)) -> None:
    """Gates the endpoints that cost something. Reads stay open.

    An unconfigured key disables the gate rather than locking everyone out, so
    a missing environment variable degrades to local-dev behaviour instead of a
    demo that 401s on every request.
    """
    expected = settings.demo_write_key
    if not expected:
        return
    if x_demo_key != expected:
        raise HTTPException(status_code=401, detail="a demo key is required for this action")


async def enforce_daily_cap() -> None:
    """The actual spend ceiling.

    Deliberately independent of the write key: the key can leak, and a cap that
    applied only to unauthenticated callers would bound nothing. Applies to
    ticket creation alone, because that is what starts a pipeline run. Reviews
    are free, and clearing the queue must never be rate limited.
    """
    used = await repo.count_tickets_last_24h()
    if used >= settings.max_tickets_per_day:
        log.warning("daily_cap_reached", used=used, cap=settings.max_tickets_per_day)
        raise HTTPException(
            status_code=429,
            detail=f"daily demo limit of {settings.max_tickets_per_day} tickets reached",
        )


ROUTE_TO_STATUS = {
    "auto_reply": "auto_replied",
    "human_review": "in_review",
    "escalate": "escalated",
}


class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    channel: Literal["web", "email", "chat"] = "web"
    customer_meta: dict[str, Any] = Field(default_factory=dict)
    external_ref: str | None = None


class TicketAccepted(BaseModel):
    ticket_id: str
    status: str


class ReviewIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    final_text: str | None = None
    note: str | None = None
    reviewer: str = "prayag"


async def process_ticket(ticket_id: str, payload: TicketIn) -> None:
    """Background execution of one pipeline run.

    Nothing may escape this function. A crashed pipeline that leaves a ticket
    at status 'received' forever is worse than a bad draft: the customer is
    waiting and no queue shows them.
    """
    structlog.contextvars.bind_contextvars(ticket_id=ticket_id)
    try:
        graph = build_graph(await get_checkpointer())
        with trace_run(ticket_id, payload.subject) as trace_id:
            final = await graph.ainvoke(
                {
                    "ticket_id": ticket_id,
                    "subject": payload.subject,
                    "body": payload.body,
                    "channel": payload.channel,
                },
                config={"configurable": {"thread_id": ticket_id}},
            )
        run_id = await repo.insert_run(ticket_id, dict(final), trace_id)
        route = str(final.get("route") or "human_review")
        await repo.update_ticket_status(ticket_id, ROUTE_TO_STATUS.get(route, "in_review"))
        log.info("ticket_processed", run_id=run_id, route=route, errors=final.get("errors", []))
    except Exception as exc:
        log.exception("pipeline_failed", error=str(exc))
        try:
            await repo.insert_run(
                ticket_id, {"errors": [f"pipeline: {type(exc).__name__}: {exc}"]}, None
            )
            await repo.update_ticket_status(ticket_id, "in_review")
        except Exception:
            log.exception("could_not_record_failure")
    finally:
        flush()
        structlog.contextvars.clear_contextvars()


@router.post(
    "/tickets",
    status_code=202,
    response_model=TicketAccepted,
    dependencies=[Depends(require_write_key), Depends(enforce_daily_cap)],
)
async def create_ticket(payload: TicketIn, background: BackgroundTasks) -> TicketAccepted:
    ticket_id = await repo.insert_ticket(
        subject=payload.subject,
        body=payload.body,
        channel=payload.channel,
        customer_meta=payload.customer_meta,
        external_ref=payload.external_ref,
    )
    background.add_task(process_ticket, ticket_id, payload)
    return TicketAccepted(ticket_id=ticket_id, status="received")


@router.get("/tickets")
async def list_tickets(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    rows = await repo.list_tickets_by_status(status, limit, offset)
    return {"tickets": rows, "limit": limit, "offset": offset}


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> dict[str, Any]:
    _validate_uuid(ticket_id)
    detail = await repo.get_ticket_detail(ticket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return detail


PIPELINE_NODES = ("classify", "retrieve", "draft", "score", "route")


@router.get("/tickets/{ticket_id}/progress")
async def ticket_progress(ticket_id: str) -> dict[str, Any]:
    """How far a running pipeline has got. Public, like the other reads.

    POST /tickets returns 202 and works in the background, so for 40-odd seconds
    a ticket exists with no run attached: agent_runs is written once, after the
    graph finishes. Polling GET /tickets/{id} during that window shows only
    status 'received' and a row of nulls.

    The per-node truth is already durable. LangGraph checkpoints state after
    every node, and each node appends its own name to node_timings_ms via the
    @timed decorator, so the checkpoint carries an ordered list of exactly which
    nodes have completed. This reads that back rather than inferring progress
    from elapsed time.
    """
    _validate_uuid(ticket_id)

    detail = await repo.get_ticket_detail(ticket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="ticket not found")

    status = str(detail["status"])
    checkpointer = await get_checkpointer()

    # Without a checkpointer the graph falls back to a per-run in-memory saver
    # that this request cannot see. Say so rather than reporting no progress,
    # which would look like a stalled pipeline.
    if checkpointer is None:
        return {
            "status": status,
            "progress_available": False,
            "completed": [],
            "skipped": [],
        }

    try:
        snapshot = await checkpointer.aget_tuple({"configurable": {"thread_id": ticket_id}})
    except Exception as exc:  # a checkpoint read must never fail a poll
        log.warning("progress_read_failed", error=str(exc))
        return {"status": status, "progress_available": False, "completed": [], "skipped": []}

    values: dict[str, Any] = (snapshot.checkpoint.get("channel_values") or {}) if snapshot else {}
    completed = [t["node"] for t in values.get("node_timings_ms", []) if t.get("node")]
    classification = values.get("classification")

    # A ticket that could not be classified skips retrieve, draft and score by
    # design. Reporting them as skipped stops a client from waiting on nodes
    # that are never going to run.
    skipped: list[str] = []
    if "classify" in completed and classification is None:
        skipped = [n for n in ("retrieve", "draft", "score") if n not in completed]

    return {
        "status": status,
        "progress_available": True,
        "completed": completed,
        "skipped": skipped,
        "classification": classification,
        "retrieved_count": len(values.get("retrieved_cases") or []),
        "errors": values.get("errors", []),
    }


@router.post(
    "/tickets/{ticket_id}/review",
    status_code=201,
    dependencies=[Depends(require_write_key)],
)
async def review_ticket(ticket_id: str, payload: ReviewIn) -> dict[str, Any]:
    _validate_uuid(ticket_id)
    detail = await repo.get_ticket_detail(ticket_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if not detail.get("run_id"):
        raise HTTPException(status_code=409, detail="ticket has no run to review yet")

    if payload.action == "edit" and not (payload.final_text or "").strip():
        raise HTTPException(status_code=422, detail="an edit must carry final_text")

    action_id = await repo.insert_review_action(
        run_id=str(detail["run_id"]),
        action=payload.action,
        final_text=payload.final_text,
        note=payload.note,
        reviewer=payload.reviewer,
    )
    new_status = "escalated" if payload.action == "reject" else "resolved"
    await repo.update_ticket_status(ticket_id, new_status)
    log.info("review_recorded", ticket_id=ticket_id, action=payload.action, status=new_status)
    return {"review_id": action_id, "status": new_status}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    _validate_uuid(run_id)
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/audit")
async def audit(
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    return {"actions": await repo.list_review_actions(limit, offset)}


def _validate_uuid(value: str) -> None:
    try:
        uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="not a valid id") from None
