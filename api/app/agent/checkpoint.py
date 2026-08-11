"""Durable checkpoints in Postgres, so a crashed run leaves a record of how far it got."""

from __future__ import annotations

from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()

_checkpointer: Any | None = None
# The context manager owns the connection; drop this and the next write finds it closed.
_manager: Any | None = None


async def get_checkpointer() -> Any | None:
    """None when Postgres is unavailable: the graph falls back to the in-memory saver."""
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
