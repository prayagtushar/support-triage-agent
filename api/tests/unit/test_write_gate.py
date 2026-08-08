"""The write gate and the daily cap.

Reads stay public so the queues, drafts and audit trail can be browsed without
signing up. The two endpoints that cost money are gated: POST /tickets spends a
pipeline run, and POST /review writes to the audit trail.

The gate is a demo key, not an identity system. It keeps crawlers and casual
abuse out; the daily cap is what actually bounds the bill, because a key shared
with interviewers is a key that can leak.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main, repo
from app.config import settings
from app.main import app
from app.routers import tickets as tickets_router

TICKET_ID = "11111111-1111-1111-1111-111111111111"
RUN_ID = "22222222-2222-2222-2222-222222222222"
KEY = "s3cret-demo-key"


@pytest.fixture(autouse=True)
def offline_lifespan(monkeypatch):
    async def noop() -> None:
        return None

    monkeypatch.setattr(repo, "open_pool", noop)
    monkeypatch.setattr(repo, "close_pool", noop)
    monkeypatch.setattr(main, "get_checkpointer", noop)
    monkeypatch.setattr(main, "close_checkpointer", noop)


@pytest.fixture
def client(monkeypatch):
    state: dict[str, Any] = {"detail": {"run_id": RUN_ID}, "daily_count": 0}

    async def fake_insert_ticket(**_: Any) -> str:
        return TICKET_ID

    async def fake_update_status(ticket_id: str, status: str) -> None:
        return None

    async def fake_detail(ticket_id: str) -> dict[str, Any] | None:
        return state["detail"]

    async def fake_insert_review(**_: Any) -> str:
        return "33333333-3333-3333-3333-333333333333"

    async def fake_count_today() -> int:
        return int(state["daily_count"])

    async def fake_process(ticket_id: str, payload: Any) -> None:
        return None

    monkeypatch.setattr(repo, "insert_ticket", fake_insert_ticket)
    monkeypatch.setattr(repo, "update_ticket_status", fake_update_status)
    monkeypatch.setattr(repo, "get_ticket_detail", fake_detail)
    monkeypatch.setattr(repo, "insert_review_action", fake_insert_review)
    monkeypatch.setattr(repo, "count_tickets_last_24h", fake_count_today)
    monkeypatch.setattr(tickets_router, "process_ticket", fake_process)

    with TestClient(app) as c:
        c.state = state  # type: ignore[attr-defined]
        yield c


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setattr(settings, "demo_write_key", KEY)


TICKET = {"subject": "charged twice", "body": "two charges on my card"}


# --- the gate is off by default -------------------------------------------


def test_no_key_configured_leaves_writes_open(client):
    """Local dev and the offline suite must not need a key. An unset key is a
    disabled gate, not an impassable one."""
    monkeypatched = settings.demo_write_key
    assert monkeypatched == ""
    assert client.post("/tickets", json=TICKET).status_code == 202


# --- the gate, once configured --------------------------------------------


def test_ticket_without_a_key_is_rejected(client, gated):
    assert client.post("/tickets", json=TICKET).status_code == 401


def test_ticket_with_a_wrong_key_is_rejected(client, gated):
    response = client.post("/tickets", json=TICKET, headers={"X-Demo-Key": "guess"})
    assert response.status_code == 401


def test_ticket_with_the_right_key_is_accepted(client, gated):
    response = client.post("/tickets", json=TICKET, headers={"X-Demo-Key": KEY})
    assert response.status_code == 202


def test_review_without_a_key_is_rejected(client, gated):
    response = client.post(f"/tickets/{TICKET_ID}/review", json={"action": "approve"})
    assert response.status_code == 401


def test_review_with_the_right_key_is_accepted(client, gated):
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Demo-Key": KEY},
    )
    assert response.status_code == 201


# --- reads stay public ----------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/tickets", f"/tickets/{TICKET_ID}", f"/runs/{RUN_ID}", "/audit", "/healthz", "/livez"],
)
def test_reads_need_no_key(client, gated, path, monkeypatch):
    async def fake_list(*_: Any, **__: Any) -> list[dict[str, Any]]:
        return []

    async def fake_run(run_id: str) -> dict[str, Any] | None:
        return {"id": RUN_ID}

    monkeypatch.setattr(repo, "list_tickets_by_status", fake_list)
    monkeypatch.setattr(repo, "list_review_actions", fake_list)
    monkeypatch.setattr(repo, "get_run", fake_run)

    assert client.get(path).status_code == 200


# --- the daily cap --------------------------------------------------------


def test_under_the_cap_is_accepted(client, gated):
    client.state["daily_count"] = settings.max_tickets_per_day - 1
    response = client.post("/tickets", json=TICKET, headers={"X-Demo-Key": KEY})
    assert response.status_code == 202


def test_at_the_cap_is_429(client, gated):
    """The cap is the real cost ceiling: a leaked key cannot run up a bill."""
    client.state["daily_count"] = settings.max_tickets_per_day
    response = client.post("/tickets", json=TICKET, headers={"X-Demo-Key": KEY})
    assert response.status_code == 429


def test_the_cap_applies_even_without_a_key_configured(client):
    """The cap is not part of the gate. It must bound spend even in the
    ungated configuration."""
    client.state["daily_count"] = settings.max_tickets_per_day
    assert client.post("/tickets", json=TICKET).status_code == 429


def test_the_cap_does_not_block_reviews(client, gated):
    """Reviews are free and clearing the queue must never be rate limited."""
    client.state["daily_count"] = settings.max_tickets_per_day
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Demo-Key": KEY},
    )
    assert response.status_code == 201
