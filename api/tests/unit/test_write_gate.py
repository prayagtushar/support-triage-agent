"""Who may write. Sending a ticket is open and bounded by the daily cap; reviewing the
reply is limited to whoever sent that ticket, so the seeded queue survives visitors."""

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
VISITOR = "visitor-abc"


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
    state: dict[str, Any] = {
        "detail": {"run_id": RUN_ID},
        "daily_count": 0,
        "visitor": None,
        "meta": None,
    }

    async def fake_insert_ticket(**kwargs: Any) -> str:
        state["meta"] = kwargs.get("customer_meta")
        return TICKET_ID

    async def fake_update_status(ticket_id: str, status: str) -> None:
        return None

    async def fake_detail(ticket_id: str) -> dict[str, Any] | None:
        return state["detail"]

    async def fake_insert_review(**_: Any) -> str:
        return "33333333-3333-3333-3333-333333333333"

    async def fake_count_today() -> int:
        return int(state["daily_count"])

    async def fake_visitor(ticket_id: str) -> str | None:
        return state["visitor"]

    async def fake_process(ticket_id: str, payload: Any) -> None:
        return None

    monkeypatch.setattr(repo, "insert_ticket", fake_insert_ticket)
    monkeypatch.setattr(repo, "update_ticket_status", fake_update_status)
    monkeypatch.setattr(repo, "get_ticket_detail", fake_detail)
    monkeypatch.setattr(repo, "insert_review_action", fake_insert_review)
    monkeypatch.setattr(repo, "count_tickets_last_24h", fake_count_today)
    monkeypatch.setattr(repo, "ticket_visitor", fake_visitor)
    monkeypatch.setattr(tickets_router, "process_ticket", fake_process)

    with TestClient(app) as c:
        c.state = state  # type: ignore[attr-defined]
        yield c


@pytest.fixture
def gated(monkeypatch):
    monkeypatch.setattr(settings, "demo_write_key", KEY)


TICKET = {"subject": "charged twice", "body": "two charges on my card"}


# --- sending a ticket is open ---------------------------------------------


def test_anyone_can_send_a_ticket(client, gated):
    """A stranger putting their own ticket through the pipeline is the point of the demo."""
    assert client.post("/tickets", json=TICKET).status_code == 202


def test_the_sender_is_recorded_so_they_can_review_the_reply(client, gated):
    client.post("/tickets", json=TICKET, headers={"X-Visitor": VISITOR})
    assert client.state["meta"]["visitor"] == VISITOR


def test_nothing_is_recorded_when_the_browser_sends_no_id(client, gated):
    client.post("/tickets", json=TICKET)
    assert "visitor" not in client.state["meta"]


# --- the daily cap is the real ceiling -------------------------------------


def test_under_the_cap_is_accepted(client, gated):
    client.state["daily_count"] = settings.max_tickets_per_day - 1
    assert client.post("/tickets", json=TICKET).status_code == 202


def test_at_the_cap_is_429(client, gated):
    """With no key on submit, the cap is the only thing standing between a script and a bill."""
    client.state["daily_count"] = settings.max_tickets_per_day
    assert client.post("/tickets", json=TICKET).status_code == 429


def test_the_cap_does_not_block_reviews(client, gated):
    """Reviews cost nothing, and clearing a queue must never be rate limited."""
    client.state["daily_count"] = settings.max_tickets_per_day
    client.state["visitor"] = VISITOR
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Visitor": VISITOR},
    )
    assert response.status_code == 201


# --- reviewing is limited to the ticket you sent ---------------------------


def test_you_can_review_the_reply_to_your_own_ticket(client, gated):
    client.state["visitor"] = VISITOR
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Visitor": VISITOR},
    )
    assert response.status_code == 201


def test_you_cannot_review_someone_else_s_ticket(client, gated):
    client.state["visitor"] = "someone-else"
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Visitor": VISITOR},
    )
    assert response.status_code == 403


def test_the_seeded_queue_is_not_reviewable_by_visitors(client, gated):
    """Seeded tickets have no sender, so no visitor owns them and the demo stays intact."""
    client.state["visitor"] = None
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Visitor": VISITOR},
    )
    assert response.status_code == 403


def test_the_owner_key_reviews_anything(client, gated):
    client.state["visitor"] = None
    response = client.post(
        f"/tickets/{TICKET_ID}/review",
        json={"action": "approve"},
        headers={"X-Demo-Key": KEY},
    )
    assert response.status_code == 201


def test_ungated_local_dev_reviews_anything(client):
    """An unset key is a disabled gate, not an impassable one."""
    client.state["visitor"] = None
    response = client.post(f"/tickets/{TICKET_ID}/review", json={"action": "approve"})
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
