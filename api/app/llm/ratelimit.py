from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Per-provider request pacing, so free-tier ceilings throttle rather than 429."""

    def __init__(self, rpm: int) -> None:
        self._min_interval = 60.0 / rpm if rpm > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self, cost: int = 1) -> None:
        """cost > 1 for batch endpoints that bill each item as a request."""
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval * cost


_limiters: dict[str, RateLimiter] = {}


def limiter_for(provider: str, rpm: int) -> RateLimiter:
    if provider not in _limiters:
        _limiters[provider] = RateLimiter(rpm)
    return _limiters[provider]
