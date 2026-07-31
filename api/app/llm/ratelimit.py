from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Paces on requests and on tokens, because providers cap both.

    Groq's free tier allows 30 requests a minute but only 12000 tokens, so a
    request-only limiter lets four long prompts blow the token ceiling while
    still looking well behaved.
    """

    def __init__(self, rpm: int, tpm: int = 0) -> None:
        self._request_interval = 60.0 / rpm if rpm > 0 else 0.0
        self._tpm = tpm
        self._lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._window_started = 0.0
        self._tokens_used = 0

    async def acquire(self, cost: int = 1, tokens: int = 0) -> None:
        if self._request_interval <= 0 and self._tpm <= 0:
            return

        async with self._lock:
            now = time.monotonic()

            if self._tpm > 0 and tokens > 0:
                if now - self._window_started >= 60.0:
                    self._window_started = now
                    self._tokens_used = 0
                if self._tokens_used + tokens > self._tpm:
                    wait = 60.0 - (now - self._window_started)
                    if wait > 0:
                        await asyncio.sleep(wait)
                        now = time.monotonic()
                    self._window_started = now
                    self._tokens_used = 0
                self._tokens_used += tokens

            if self._request_interval > 0:
                wait = self._next_request_at - now
                if wait > 0:
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                self._next_request_at = now + self._request_interval * cost


_limiters: dict[str, RateLimiter] = {}


def limiter_for(provider: str, rpm: int, tpm: int = 0) -> RateLimiter:
    if provider not in _limiters:
        _limiters[provider] = RateLimiter(rpm, tpm)
    return _limiters[provider]
