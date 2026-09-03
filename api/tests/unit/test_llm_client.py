import httpx
import pytest
from openai import APIConnectionError
from pydantic import BaseModel

from app.errors import ModelOutputInvalid
from app.llm import client as client_module


class Toy(BaseModel):
    intent: str
    confidence: float


def fake_transport(responses: list[str]):
    """Stands in for app.llm.client._call, the module's single transport seam."""
    calls: list[list[dict[str, str]]] = []

    async def _call(*, provider, model, messages, temperature, json_mode, max_tokens=None):
        calls.append(list(messages))
        return responses[len(calls) - 1], 10, 5, 1

    return _call, calls


async def test_valid_first_response_makes_one_call(monkeypatch):
    call, calls = fake_transport(['{"intent": "billing", "confidence": 0.9}'])
    monkeypatch.setattr(client_module, "_call", call)

    parsed, stats = await client_module.complete_json(
        provider="groq", model="llama-3.3-70b-versatile", system="s", user="u", schema=Toy
    )

    assert parsed.intent == "billing"
    assert len(calls) == 1
    assert stats.prompt_tokens == 10


async def test_invalid_output_triggers_exactly_one_corrective_retry(monkeypatch):
    call, calls = fake_transport(
        ['{"intent": "billing"}', '{"intent": "billing", "confidence": 0.7}']
    )
    monkeypatch.setattr(client_module, "_call", call)

    parsed, stats = await client_module.complete_json(
        provider="groq", model="llama-3.3-70b-versatile", system="s", user="u", schema=Toy
    )

    assert parsed.confidence == 0.7
    assert len(calls) == 2
    # The retry carries the validation error back to the model.
    assert "failed schema validation" in calls[1][-1]["content"]
    # Tokens accumulate across both attempts rather than reporting only the last.
    assert stats.prompt_tokens == 20


async def test_second_failure_raises_with_both_raw_outputs(monkeypatch):
    call, _ = fake_transport(['{"intent": "billing"}', "still not valid"])
    monkeypatch.setattr(client_module, "_call", call)

    with pytest.raises(ModelOutputInvalid) as exc:
        await client_module.complete_json(
            provider="groq", model="llama-3.3-70b-versatile", system="s", user="u", schema=Toy
        )

    assert len(exc.value.attempts) == 2


async def test_fenced_json_is_recovered_without_a_retry(monkeypatch):
    call, calls = fake_transport(['```json\n{"intent": "refund", "confidence": 0.5}\n```'])
    monkeypatch.setattr(client_module, "_call", call)

    parsed, _ = await client_module.complete_json(
        provider="groq", model="llama-3.3-70b-versatile", system="s", user="u", schema=Toy
    )

    assert parsed.intent == "refund"
    assert len(calls) == 1


class _Delta:
    def __init__(self, content: str | None) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str | None) -> None:
        self.delta = _Delta(content)


class _Usage:
    def __init__(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion


class _Event:
    def __init__(self, content: str | None = None, usage: _Usage | None = None) -> None:
        self.choices = [_Choice(content)] if content is not None else []
        self.usage = usage


def fake_stream(pieces: list[str], *, usage: _Usage | None = None, fail_times: int = 0):
    """Stands in for the OpenAI client. Returns the fake and a call counter."""
    attempts = {"n": 0}

    class _Completions:
        async def create(self, **kwargs):
            attempts["n"] += 1
            if attempts["n"] <= fail_times:
                raise APIConnectionError(request=httpx.Request("POST", "http://x"))

            async def _gen():
                for piece in pieces:
                    yield _Event(piece)
                if usage is not None:
                    yield _Event(usage=usage)

            return _gen()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    return _Client(), attempts


async def test_stream_yields_pieces_and_accumulates_the_same_text(monkeypatch):
    fake, _ = fake_stream(["Hello", " there", "."], usage=_Usage(10, 3))
    monkeypatch.setattr(client_module, "get_client", lambda _: fake)

    stream = client_module.stream_text(provider="groq", model="m", system="s", user="u")
    pieces = [chunk async for chunk in stream]

    assert pieces == ["Hello", " there", "."]
    # The whole point: what was streamed and what is stored must not diverge.
    assert stream.text == "Hello there."
    assert stream.stats is not None
    assert stream.stats.completion_tokens == 3
    assert stream.first_token_ms is not None


async def test_stream_retries_before_the_first_chunk(monkeypatch):
    fake, attempts = fake_stream(["ok"], fail_times=1)
    monkeypatch.setattr(client_module, "get_client", lambda _: fake)
    monkeypatch.setattr(client_module.settings, "llm_max_backoff_seconds", 0.0)

    stream = client_module.stream_text(provider="groq", model="m", system="s", user="u")
    assert [c async for c in stream] == ["ok"]
    assert attempts["n"] == 2
    assert stream.stats is not None and stream.stats.attempts == 2


async def test_missing_usage_still_produces_costable_stats(monkeypatch):
    fake, _ = fake_stream(["abcd" * 10])
    monkeypatch.setattr(client_module, "get_client", lambda _: fake)

    stream = client_module.stream_text(provider="groq", model="m", system="s", user="u")
    async for _ in stream:
        pass

    # No usage event: estimated rather than zero, so a streamed call is never free.
    assert stream.stats is not None
    assert stream.stats.completion_tokens == 10
