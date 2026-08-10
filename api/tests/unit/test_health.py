from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_livez() -> None:
    """The path the deployed service is actually probed on.

    /healthz cannot serve this purpose on Cloud Run: Google Frontend returns its
    own 404 for that exact path before the request reaches the container.
    """
    resp = client.get("/livez")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_healthz_still_works_as_an_alias() -> None:
    """Kept for the in-container Docker HEALTHCHECK and non-Google hosts."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
