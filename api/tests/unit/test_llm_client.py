import pytest
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
