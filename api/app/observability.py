"""Langfuse tracing: a lens, not a dependency. Every call here swallows its own failures."""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()

_client: Any | None = None


def get_client() -> Any | None:
    global _client
    if not settings.langfuse_enabled:
        return None
    if _client is None:
        try:
            from langfuse import Langfuse

            _client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except Exception as exc:
            log.warning("langfuse_init_failed", error=str(exc))
            return None
    return _client


@contextlib.contextmanager
def trace_run(ticket_id: str, subject: str) -> Iterator[str | None]:
    client = get_client()
    if client is None:
        yield None
        return

    trace_id: str | None = None
    try:
        with client.start_as_current_observation(
            name="triage", as_type="span", input={"subject": subject}
        ):
            client.update_current_span(metadata={"ticket_id": ticket_id})
            trace_id = client.get_current_trace_id()
            yield trace_id
    except Exception as exc:
        log.warning("langfuse_trace_failed", error=str(exc), ticket_id=ticket_id)
        yield trace_id


def flush() -> None:
    client = get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        log.warning("langfuse_flush_failed", error=str(exc))
