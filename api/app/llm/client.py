from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, ValidationError

from app.config import Provider, settings
from app.errors import ModelOutputInvalid, ModelOutputTruncated, ProviderUnavailable
from app.llm.parsing import extract_json_object
from app.llm.pricing import estimate_inr
from app.llm.providers import get_client, get_provider
from app.llm.ratelimit import limiter_for

_RETRYABLE_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class CallStats:
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_inr: float | None
    attempts: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "estimated_cost_inr": self.estimated_cost_inr,
            "attempts": self.attempts,
        }


def _backoff(attempt: int, retry_after: float | None) -> float:
    base = retry_after if retry_after is not None else min(2.0**attempt, 8.0)
    # Cap it, so a provider asking for minutes fails visibly instead of looking like a hang.
    return min(base, settings.llm_max_backoff_seconds) + random.uniform(0, 0.5)  # noqa: S311


def _retry_after_seconds(exc: APIStatusError) -> float | None:
    raw = exc.response.headers.get("retry-after") if exc.response is not None else None
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


async def _call(
    *,
    provider: Provider,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    json_mode: bool,
    max_tokens: int | None,
) -> tuple[str, int, int, int]:
    config = get_provider(provider)
    client = get_client(provider)
    limiter = limiter_for(provider, config.rpm, config.tpm)

    # Rough on purpose: pacing needs a number before the call, and 4 chars/token is close enough.
    estimated_tokens = sum(len(m["content"]) for m in messages) // 4 + (max_tokens or 0)

    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_error: Exception | None = None
    for attempt in range(settings.llm_max_transport_retries + 1):
        await limiter.acquire(tokens=estimated_tokens)
        try:
            response = await client.chat.completions.create(**kwargs)
        except APIStatusError as exc:
            # Rejecting response_format is a capability gap, not a fault. Retry without it.
            if json_mode and exc.status_code == 400 and "response_format" in str(exc).lower():
                kwargs.pop("response_format", None)
                json_mode = False
                last_error = exc
                continue
            if exc.status_code not in _RETRYABLE_STATUS:
                raise ProviderUnavailable(f"{provider}/{model} returned {exc.status_code}") from exc
            last_error = exc
            await asyncio.sleep(_backoff(attempt, _retry_after_seconds(exc)))
        except (APIConnectionError, APITimeoutError) as exc:
            last_error = exc
            await asyncio.sleep(_backoff(attempt, None))
        else:
            choice = response.choices[0]
            content = choice.message.content or ""
            if not content.strip() and choice.finish_reason == "length":
                raise ModelOutputTruncated(
                    f"{provider}/{model} spent its {max_tokens} token budget without "
                    "producing content; raise the budget for this node"
                )
            usage = response.usage
            return (
                content,
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
                attempt + 1,
            )

    raise ProviderUnavailable(
        f"{provider}/{model} failed after {settings.llm_max_transport_retries + 1} attempts: "
        f"{type(last_error).__name__}: {last_error}"
    ) from last_error


def _stats(
    provider: Provider, model: str, started: float, prompt: int, completion: int, attempts: int
) -> CallStats:
    return CallStats(
        provider=provider,
        model=model,
        latency_ms=int((time.monotonic() - started) * 1000),
        prompt_tokens=prompt,
        completion_tokens=completion,
        estimated_cost_inr=estimate_inr(model, prompt, completion, settings.usd_to_inr),
        attempts=attempts,
    )


async def complete_text(
    *,
    provider: Provider,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> tuple[str, CallStats]:
    started = time.monotonic()
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    content, prompt, completion, attempts = await _call(
        provider=provider,
        model=model,
        messages=messages,
        temperature=temperature,
        json_mode=False,
        max_tokens=max_tokens,
    )
    return content, _stats(provider, model, started, prompt, completion, attempts)


async def complete_json[T: BaseModel](
    *,
    provider: Provider,
    model: str,
    system: str,
    user: str,
    schema: type[T],
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> tuple[T, CallStats]:
    started = time.monotonic()
    messages = [
        {"role": "system", "content": f"{system}\n\nSCHEMA:\n{schema.model_json_schema()}"},
        {"role": "user", "content": user},
    ]

    raw_attempts: list[str] = []
    total_prompt = total_completion = total_attempts = 0

    for correction in range(settings.llm_max_validation_retries + 1):
        content, prompt, completion, attempts = await _call(
            provider=provider,
            model=model,
            messages=messages,
            temperature=temperature,
            json_mode=True,
            max_tokens=max_tokens,
        )
        total_prompt += prompt
        total_completion += completion
        total_attempts += attempts
        raw_attempts.append(content)

        try:
            parsed = schema.model_validate_json(extract_json_object(content))
        except ValidationError as exc:
            if correction >= settings.llm_max_validation_retries:
                raise ModelOutputInvalid(model, raw_attempts, str(exc)) from exc
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"That output failed schema validation with:\n{exc}\n\n"
                        "Return only a corrected JSON object matching the schema."
                    ),
                }
            )
        else:
            return parsed, _stats(
                provider, model, started, total_prompt, total_completion, total_attempts
            )

    raise AssertionError("unreachable")


class TextStream:
    """A streamed completion.

    Yields text chunks as they arrive. `text` and `stats` are complete once the
    iteration ends.

        stream = stream_text(provider=..., model=..., system=..., user=...)
        async for chunk in stream:
            speak(chunk)
        store(stream.text, stream.stats)

    Retries stop at the first chunk. Before that a failure is invisible and can be
    retried; after it the caller has already spoken half a sentence, so re-running
    the call would say it twice.
    """

    def __init__(
        self,
        *,
        provider: Provider,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._messages = messages
        self._temperature = temperature
        self._max_tokens = max_tokens
        self.text = ""
        self.stats: CallStats | None = None
        self.first_token_ms: int | None = None

    async def __aiter__(self) -> AsyncIterator[str]:
        config = get_provider(self._provider)
        client = get_client(self._provider)
        limiter = limiter_for(self._provider, config.rpm, config.tpm)
        estimated_tokens = sum(len(m["content"]) for m in self._messages) // 4 + (
            self._max_tokens or 0
        )

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": self._messages,
            "temperature": self._temperature,
            "stream": True,
            # Not universal. Dropped on the first provider that rejects it.
            "stream_options": {"include_usage": True},
        }
        if self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens

        started = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(settings.llm_max_transport_retries + 1):
            await limiter.acquire(tokens=estimated_tokens)
            try:
                response = await client.chat.completions.create(**kwargs)
                async for event in response:
                    usage = getattr(event, "usage", None)
                    if usage is not None:
                        self._prompt_tokens = usage.prompt_tokens
                        self._completion_tokens = usage.completion_tokens
                    if not event.choices:
                        continue
                    piece = event.choices[0].delta.content
                    if not piece:
                        continue
                    if self.first_token_ms is None:
                        self.first_token_ms = int((time.monotonic() - started) * 1000)
                    self.text += piece
                    yield piece
            except APIStatusError as exc:
                if "stream_options" in str(exc).lower() and "stream_options" in kwargs:
                    kwargs.pop("stream_options")
                    last_error = exc
                    continue
                if self.text or exc.status_code not in _RETRYABLE_STATUS:
                    raise ProviderUnavailable(
                        f"{self._provider}/{self._model} returned {exc.status_code}"
                    ) from exc
                last_error = exc
                await asyncio.sleep(_backoff(attempt, _retry_after_seconds(exc)))
            except (APIConnectionError, APITimeoutError) as exc:
                if self.text:
                    raise ProviderUnavailable(
                        f"{self._provider}/{self._model} died mid-stream after "
                        f"{len(self.text)} characters"
                    ) from exc
                last_error = exc
                await asyncio.sleep(_backoff(attempt, None))
            else:
                self.stats = _stats(
                    self._provider,
                    self._model,
                    started,
                    getattr(self, "_prompt_tokens", 0),
                    # Providers that omit usage on streams still have to be costed.
                    getattr(self, "_completion_tokens", 0) or len(self.text) // 4,
                    attempt + 1,
                )
                return

        raise ProviderUnavailable(
            f"{self._provider}/{self._model} failed after "
            f"{settings.llm_max_transport_retries + 1} attempts: "
            f"{type(last_error).__name__}: {last_error}"
        ) from last_error


def stream_text(
    *,
    provider: Provider,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> TextStream:
    return TextStream(
        provider=provider,
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
