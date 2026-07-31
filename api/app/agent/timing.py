from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from app.agent.state import TriageState

NodeFn = Callable[[TriageState], Awaitable[dict[str, Any]]]


def timed(name: str) -> Callable[[NodeFn], NodeFn]:
    """Records per-node latency into state. Also the seam tracing hooks into."""

    def decorate(fn: NodeFn) -> NodeFn:
        @wraps(fn)
        async def wrapper(state: TriageState) -> dict[str, Any]:
            started = time.monotonic()
            update = await fn(state)
            elapsed = int((time.monotonic() - started) * 1000)
            update.setdefault("node_timings_ms", [])
            update["node_timings_ms"] = [*update["node_timings_ms"], {"node": name, "ms": elapsed}]
            return update

        return wrapper

    return decorate
