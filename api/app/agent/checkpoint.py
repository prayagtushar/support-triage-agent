"""Durable checkpoints in Postgres.

LangGraph persists state after every node, keyed by thread_id. At portfolio
scale nothing resumes automatically; the point is that a crashed run leaves an
inspectable record of how far it got, rather than nothing.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()

_checkpointer: Any | None = None
# The context manager owns the connection. Dropping this reference lets it be
# collected, and the next write fails with "the connection is closed".
_manager: Any | None = None


async def get_checkpointer() -> Any | None:
    """Returns None when Postgres checkpointing is unavailable.

    A checkpointer that cannot start must not stop tickets being triaged, so
    the graph falls back to the in-memory saver.
    """
    global _checkpointer, _manager
    if _checkpointer is not None:
        return _checkpointer
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        _manager = AsyncPostgresSaver.from_conn_string(settings.database_url)
        _checkpointer = await _manager.__aenter__()
        await _checkpointer.setup()
    except Exception as exc:
        log.warning("checkpointer_unavailable", error=str(exc))
        _manager = None
        _checkpointer = None
        return None
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _manager
    if _manager is not None:
        try:
            await _manager.__aexit__(None, None, None)
        except Exception as exc:
            log.warning("checkpointer_close_failed", error=str(exc))
    _manager = None
    _checkpointer = None
