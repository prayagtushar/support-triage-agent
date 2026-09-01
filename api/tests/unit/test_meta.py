"""The surfaces the dashboard reads: /policy, /status and ticket progress. All offline."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main, repo
from app.config import settings
from app.main import app
from app.routers import tickets as tickets_router

TICKET_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def offline_lifespan(monkeypatch):
    async def noop() -> None:
        return None

    monkeypatch.setattr(repo, "open_pool", noop)
    monkeypatch.setattr(repo, "close_pool", noop)
    monkeypatch.setattr(main, "get_checkpointer", noop)
    monkeypatch.setattr(main, "close_checkpointer", noop)


# --- /policy ---------------------------------------------------------------


def test_policy_reports_the_thresholds_actually_in_force():
    """The dashboard draws its threshold line from this, so it must be the live value."""
    with TestClient(app) as c:
        body = c.get("/policy").json()

    assert body["thresholds"]["auto_reply"] == settings.route_auto_reply_threshold
    assert body["thresholds"]["review"] == settings.route_review_threshold
    assert body["composite_weights"]["judge"] == settings.composite_weight_judge


def test_policy_weights_sum_to_one():
    with TestClient(app) as c:
        weights = c.get("/policy").json()["composite_weights"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_policy_names_a_different_vendor_for_judge_and_drafter():
    """Cross-vendor judging is the invariant Settings refuses to boot without."""
    with TestClient(app) as c:
        models = c.get("/policy").json()["models"]
    assert models["judge"].split("/")[0] != models["drafter"].split("/")[0]


# --- /status ---------------------------------------------------------------


def _status_client(monkeypatch, health: dict[str, Any], last_24h: int = 3):
    async def fake_health(last: int) -> dict[str, Any]:
        return health

    async def fake_count() -> int:
        return last_24h

    async def fake_last_run() -> str | None:
        return "2026-08-31T10:00:00+00:00"

    async def fake_reasons() -> dict[str, int]:
        return {"hallucinated": 2}

    monkeypatch.setattr(repo, "recent_run_health", fake_health)
    monkeypatch.setattr(repo, "count_tickets_last_24h", fake_count)
    monkeypatch.setattr(repo, "last_run_at", fake_last_run)
    monkeypatch.setattr(repo, "reject_reason_counts", fake_reasons)
    return TestClient(app)


def test_status_is_healthy_when_retrieval_is_producing_cases(monkeypatch):
    with _status_client(
        monkeypatch,
        {"total": 50, "with_errors": 3, "empty_retrieval": 1, "routes": {"human_review": 50}},
    ) as c:
        body = c.get("/status").json()

    assert body["degraded"] is False
    assert body["empty_retrieval_rate"] == 0.02


def test_status_flags_the_outage_that_actually_happened(monkeypatch):
    """Every run finished, nothing errored, and retrieval returned nothing on all of them."""
    with _status_client(
        monkeypatch,
        {"total": 2, "with_errors": 2, "empty_retrieval": 2, "routes": {"human_review": 2}},
    ) as c:
        body = c.get("/status").json()

    assert body["degraded"] is True
    assert "2 of 2" in body["reason"]


def test_status_degrades_on_empty_retrieval_even_with_no_recorded_errors(monkeypatch):
    """An empty list is not an error, but the drafter still had nothing to ground on."""
    with _status_client(
        monkeypatch,
        {"total": 10, "with_errors": 0, "empty_retrieval": 9, "routes": {"human_review": 10}},
    ) as c:
        body = c.get("/status").json()

    assert body["degraded"] is True
    assert body["error_rate"] == 0.0


def test_status_says_nothing_is_wrong_before_any_runs_exist(monkeypatch):
    with _status_client(
        monkeypatch, {"total": 0, "with_errors": 0, "empty_retrieval": 0, "routes": {}}
    ) as c:
        body = c.get("/status").json()

    assert body["degraded"] is False
    assert body["runs"] == 0
    assert body["last_run_at"] is None


def test_status_carries_a_heartbeat_when_runs_exist(monkeypatch):
    """Silence is ambiguous. A healthy system has to say when it last did anything."""
    with _status_client(
        monkeypatch,
        {"total": 5, "with_errors": 0, "empty_retrieval": 0, "routes": {"human_review": 5}},
    ) as c:
        body = c.get("/status").json()

    assert body["last_run_at"] == "2026-08-31T10:00:00+00:00"


# --- ticket progress -------------------------------------------------------


class FakeCheckpointer:
    def __init__(self, values: dict[str, Any] | None, raises: bool = False):
        self._values = values
        self._raises = raises

    async def aget_tuple(self, _config: dict[str, Any]) -> Any:
        if self._raises:
            raise RuntimeError("checkpoint table is gone")
        if self._values is None:
            return None
        return type("Snapshot", (), {"checkpoint": {"channel_values": self._values}})()


def _progress_client(monkeypatch, detail, checkpointer):
    async def fake_detail(ticket_id: str):
        return detail

    async def fake_checkpointer():
        return checkpointer

    monkeypatch.setattr(repo, "get_ticket_detail", fake_detail)
    monkeypatch.setattr(tickets_router, "get_checkpointer", fake_checkpointer)
    return TestClient(app)


def test_progress_lists_completed_nodes_in_order(monkeypatch):
    values = {
        "node_timings_ms": [
            {"node": "classify", "ms": 8000},
            {"node": "retrieve", "ms": 500},
        ],
        "classification": {"intent": "billing"},
        "retrieved_cases": [{}, {}, {}],
    }
    with _progress_client(monkeypatch, {"status": "received"}, FakeCheckpointer(values)) as c:
        body = c.get(f"/tickets/{TICKET_ID}/progress").json()

    assert body["completed"] == ["classify", "retrieve"]
    assert body["retrieved_count"] == 3
    assert body["skipped"] == []


def test_progress_marks_the_expensive_nodes_skipped_when_classification_failed(monkeypatch):
    """Those nodes are never going to run, so a client must not sit waiting on them."""
    values = {
        "node_timings_ms": [{"node": "classify", "ms": 8000}],
        "classification": None,
    }
    with _progress_client(monkeypatch, {"status": "received"}, FakeCheckpointer(values)) as c:
        body = c.get(f"/tickets/{TICKET_ID}/progress").json()

    assert body["skipped"] == ["retrieve", "draft", "score"]


def test_progress_reports_no_progress_when_nothing_is_checkpointed_yet(monkeypatch):
    with _progress_client(monkeypatch, {"status": "received"}, FakeCheckpointer(None)) as c:
        body = c.get(f"/tickets/{TICKET_ID}/progress").json()

    assert body["completed"] == []
    assert body["progress_available"] is True


def test_progress_admits_it_cannot_see_an_in_memory_saver(monkeypatch):
    """Saying so beats reporting a stalled pipeline."""
    with _progress_client(monkeypatch, {"status": "received"}, None) as c:
        body = c.get(f"/tickets/{TICKET_ID}/progress").json()

    assert body["progress_available"] is False


def test_progress_survives_a_failing_checkpoint_read(monkeypatch):
    """Polling must never 500: a broken read is a lost progress bar, not a lost ticket."""
    with _progress_client(
        monkeypatch, {"status": "received"}, FakeCheckpointer(None, raises=True)
    ) as c:
        response = c.get(f"/tickets/{TICKET_ID}/progress")

    assert response.status_code == 200
    assert response.json()["progress_available"] is False


def test_progress_404s_for_an_unknown_ticket(monkeypatch):
    with _progress_client(monkeypatch, None, FakeCheckpointer(None)) as c:
        assert c.get(f"/tickets/{TICKET_ID}/progress").status_code == 404


def test_progress_rejects_a_malformed_id(monkeypatch):
    """422, matching the other id-taking routes, rather than a 500 from uuid.UUID."""
    with _progress_client(monkeypatch, None, FakeCheckpointer(None)) as c:
        assert c.get("/tickets/not-a-uuid/progress").status_code == 422


def test_policy_states_the_domain_the_numbers_were_measured_under():
    """The classifier and drafter both work from it, so a reader of /policy should see the
    assumption rather than infer it from the intent list."""
    with TestClient(app) as c:
        body = c.get("/policy").json()

    assert body["domain"] == settings.domain
    assert body["domain"]
