"""Endpoint tests with the repository faked, so they run offline in milliseconds."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main, repo
from app.main import app
from app.routers import tickets as tickets_router

TICKET_ID = "11111111-1111-1111-1111-111111111111"
RUN_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def offline_lifespan(monkeypatch):
    """Faking the repo functions is not enough: entering TestClient runs the
    lifespan, which opens a real pool and checkpointer before any route is hit."""

    async def noop() -> None:
        return None

    monkeypatch.setattr(repo, "open_pool", noop)
    monkeypatch.setattr(repo, "close_pool", noop)
    monkeypatch.setattr(main, "get_checkpointer", noop)
    monkeypatch.setattr(main, "close_checkpointer", noop)


@pytest.fixture
def client(monkeypatch):
    """Replaces the persistence seam. The API is testable without a database
    for the same reason the agent is testable without HTTP."""
    state: dict[str, Any] = {"status": None, "reviews": [], "detail": None, "background": []}

    async def fake_insert_ticket(**_: Any) -> str:
        return TICKET_ID

    async def fake_update_status(ticket_id: str, status: str) -> None:
        state["status"] = status

    async def fake_detail(ticket_id: str) -> dict[str, Any] | None:
        return state["detail"]

    async def fake_insert_review(**kwargs: Any) -> str:
        state["reviews"].append(kwargs)
        return "33333333-3333-3333-3333-333333333333"

    async def fake_list(status: str | None, limit: int, offset: int) -> list[dict[str, Any]]:
        return [{"id": TICKET_ID, "subject": "hi", "status": status or "received"}]

    async def fake_run(run_id: str) -> dict[str, Any] | None:
        return {"id": RUN_ID, "route": "human_review"} if run_id == RUN_ID else None

    async def fake_actions(limit: int, offset: int) -> list[dict[str, Any]]:
        return []

    # The daily cap runs as a dependency on POST /tickets, so it hits the
    # repository before any handler body does. The cap itself is covered in
    # test_write_gate.py; here it just has to stay out of the way.
    async def fake_count_today() -> int:
        return 0

    monkeypatch.setattr(repo, "insert_ticket", fake_insert_ticket)
    monkeypatch.setattr(repo, "update_ticket_status", fake_update_status)
    monkeypatch.setattr(repo, "get_ticket_detail", fake_detail)
    monkeypatch.setattr(repo, "insert_review_action", fake_insert_review)
    monkeypatch.setattr(repo, "list_tickets_by_status", fake_list)
    monkeypatch.setattr(repo, "get_run", fake_run)
    monkeypatch.setattr(repo, "list_review_actions", fake_actions)
    monkeypatch.setattr(repo, "count_tickets_last_24h", fake_count_today)

    # The pipeline is exercised in its own tests; here it must not run.
    async def fake_process(ticket_id: str, payload: Any) -> None:
        state["background"].append(ticket_id)

    monkeypatch.setattr(tickets_router, "process_ticket", fake_process)

    with TestClient(app) as c:
        c.state = state  # type: ignore[attr-defined]
        yield c


def test_healthz_does_not_need_the_database():
    with TestClient(app) as c:
        assert c.get("/healthz").json()["status"] == "ok"


def test_post_ticket_returns_202_and_an_id(client):
    response = client.post("/tickets", json={"subject": "charged twice", "body": "two charges"})
    assert response.status_code == 202
    assert response.json() == {"ticket_id": TICKET_ID, "status": "received"}


def test_post_ticket_rejects_an_empty_body(client):
    assert client.post("/tickets", json={"subject": "x", "body": ""}).status_code == 422


def test_post_ticket_rejects_an_unknown_channel(client):
    response = client.post(
        "/tickets", json={"subject": "x", "body": "y", "channel": "carrier-pigeon"}
    )
    assert response.status_code == 422


def test_get_unknown_ticket_is_404(client):
    client.state["detail"] = None
    assert client.get(f"/tickets/{TICKET_ID}").status_code == 404


def test_malformed_id_is_422_not_500(client):
    assert client.get("/tickets/not-a-uuid").status_code == 422


def test_review_approve_resolves_the_ticket(client):
    client.state["detail"] = {"run_id": RUN_ID}
    response = client.post(f"/tickets/{TICKET_ID}/review", json={"action": "approve"})
    assert response.status_code == 201
    assert response.json()["status"] == "resolved"
    assert client.state["status"] == "resolved"


def test_review_reject_escalates(client):
    client.state["detail"] = {"run_id": RUN_ID}
    response = client.post(f"/tickets/{TICKET_ID}/review", json={"action": "reject"})
    assert response.json()["status"] == "escalated"


def test_edit_without_text_is_rejected(client):
    """Every 'edit' row must carry what the human actually preferred, or it is
    not labelled data."""
    client.state["detail"] = {"run_id": RUN_ID}
    response = client.post(
        f"/tickets/{TICKET_ID}/review", json={"action": "edit", "final_text": "   "}
    )
    assert response.status_code == 422


def test_edit_with_text_is_stored(client):
    client.state["detail"] = {"run_id": RUN_ID}
    response = client.post(
        f"/tickets/{TICKET_ID}/review", json={"action": "edit", "final_text": "better wording"}
    )
    assert response.status_code == 201
    assert client.state["reviews"][0]["final_text"] == "better wording"


def test_reviewing_a_ticket_with_no_run_is_409(client):
    client.state["detail"] = {"run_id": None}
    assert (
        client.post(f"/tickets/{TICKET_ID}/review", json={"action": "approve"}).status_code == 409
    )


def test_queue_listing_passes_the_status_filter_through(client):
    body = client.get("/tickets", params={"status": "in_review"}).json()
    assert body["tickets"][0]["status"] == "in_review"


def test_queue_listing_rejects_an_absurd_limit(client):
    assert client.get("/tickets", params={"limit": 5000}).status_code == 422


def test_unknown_run_is_404(client):
    assert client.get(f"/runs/{TICKET_ID}").status_code == 404
