import time

from app.llm.ratelimit import RateLimiter


async def test_requests_are_spaced_by_the_interval():
    limiter = RateLimiter(rpm=600)  # 0.1s apart
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    assert time.monotonic() - start >= 0.2


async def test_batch_cost_multiplies_the_spacing():
    """A batch endpoint bills each item, so one call must reserve that much room."""
    limiter = RateLimiter(rpm=600)
    await limiter.acquire(cost=5)
    start = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - start >= 0.4


async def test_token_ceiling_forces_a_wait_within_the_window():
    """Groq's real constraint: plenty of requests left, no tokens left."""
    limiter = RateLimiter(rpm=0, tpm=1000)
    await limiter.acquire(tokens=900)
    start = time.monotonic()
    limiter._window_started = time.monotonic() - 59.8
    await limiter.acquire(tokens=900)
    assert time.monotonic() - start >= 0.1


async def test_token_pacing_is_skipped_when_tpm_is_unset():
    limiter = RateLimiter(rpm=0, tpm=0)
    start = time.monotonic()
    await limiter.acquire(tokens=10_000_000)
    assert time.monotonic() - start < 0.05
