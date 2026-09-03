"""Multiple desks in one deployment. All offline: the registry is seeded in conftest."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import domains, main, repo
from app.agent.prompts.classify import build_classify_prompt
from app.agent.schemas import classification_for
from app.main import app
from tests.conftest import ECOM, TECH


@pytest.fixture(autouse=True)
def offline_lifespan(monkeypatch):
    async def noop() -> None:
        return None

    monkeypatch.setattr(repo, "open_pool", noop)
    monkeypatch.setattr(repo, "close_pool", noop)
    monkeypatch.setattr(main, "get_checkpointer", noop)
    monkeypatch.setattr(main, "close_checkpointer", noop)


def _client(monkeypatch, counts: dict[str, Any] | None = None):
    async def fake_counts() -> dict[str, Any]:
        return (
            counts
            if counts is not None
            else {"ecom": {"cases": 3400, "embedded": 3400, "synthetic": 400}}
        )

    async def fake_queues() -> list[dict[str, Any]]:
        return [
            {
                "domain_id": "ecom",
                "tickets": 60,
                "in_review": 40,
                "auto_replied": 10,
                "escalated": 10,
            }
        ]

    monkeypatch.setattr(repo, "domain_case_counts", fake_counts)
    monkeypatch.setattr(repo, "domain_queue_counts", fake_queues)
    return TestClient(app)


def test_domains_lists_every_desk(monkeypatch):
    with _client(monkeypatch) as c:
        body = c.get("/domains").json()

    assert [d["id"] for d in body["domains"]] == ["ecom", "tech"]
    assert body["default"] == "ecom"


def test_a_desk_with_no_embedded_cases_is_not_ready(monkeypatch):
    """The difference is invisible from the queue screen and changes what every draft means."""
    with _client(monkeypatch) as c:
        body = c.get("/domains").json()

    desks = {d["id"]: d for d in body["domains"]}
    assert desks["ecom"]["ready"] is True
    assert desks["tech"]["ready"] is False
    assert desks["tech"]["cases"] == 0


def test_provenance_reaches_the_client(monkeypatch):
    """A reviewer needs to know they are in the generated desk before judging citations."""
    with _client(monkeypatch) as c:
        desks = {d["id"]: d for d in c.get("/domains").json()["domains"]}

    assert desks["ecom"]["provenance"] == "real"
    assert desks["tech"]["provenance"] == "synthetic"


def test_each_desk_gets_its_own_taxonomy():
    assert "shipping" in ECOM.intents
    assert "shipping" not in TECH.intents
    assert "outage" in TECH.intents
    assert "outage" not in ECOM.intents


def test_classification_rejects_an_intent_from_another_desk():
    """The taxonomy left the CHECK constraint; it must not have left validation."""
    model = classification_for(TECH.intents)
    payload = (
        '{"intent": "%s", "urgency": "P2", "language": "en", '
        '"sentiment": "neutral", "confidence": 0.9, "rationale": "x"}'
    )

    assert model.model_validate_json(payload % "outage").intent == "outage"
    with pytest.raises(ValueError):
        model.model_validate_json(payload % "shipping")


def test_the_model_is_shown_only_its_own_desks_intents():
    """The enum reaches the JSON schema, so a wrong intent is corrected on the retry."""
    schema = classification_for(TECH.intents).model_json_schema()
    assert set(schema["properties"]["intent"]["enum"]) == set(TECH.intents)


def test_the_prompt_is_built_from_the_desk_not_from_code():
    ecom = build_classify_prompt(ECOM)
    tech = build_classify_prompt(TECH)

    assert "a consumer online shopping service" in ecom
    assert "a consumer software and devices support desk" in tech
    # Generic instructions survive per desk; they are about tickets, not about a business.
    for prompt in (ecom, tech):
        assert "URGENCY DEFINITIONS" in prompt
        assert "LANGUAGE RULE" in prompt
        assert "RATIONALE:" in prompt


async def test_an_unknown_desk_is_named_rather_than_guessed():
    with pytest.raises(domains.UnknownDomain) as caught:
        await domains.get("finance")

    assert "finance" in str(caught.value)
    assert "ecom" in str(caught.value)
