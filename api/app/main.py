from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import repo
from app.agent.checkpoint import close_checkpointer, get_checkpointer
from app.config import settings
from app.logging import configure_logging
from app.routers.tickets import router as tickets_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    await repo.open_pool()
    await get_checkpointer()
    log.info("api_started", env=settings.app_env)
    try:
        yield
    finally:
        await close_checkpointer()
        await repo.close_pool()


app = FastAPI(title="Support Triage Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tickets_router)


# Liveness is served at /livez, not /healthz, because Google Frontend swallows
# /healthz before it reaches a Cloud Run container: that one path returns
# Google's own HTML 404, while every other unrouted path (including /healthz2)
# returns this app's JSON 404. So a /healthz probe against the deployed service
# can never pass, no matter what the container does.
#
# /healthz stays registered as an alias. It is reachable inside the container
# and on any host that is not behind Google Frontend, which is what the Docker
# HEALTHCHECK and the local test suite use.
@app.get("/livez")
@app.get("/healthz", include_in_schema=False)
def livez() -> dict[str, str]:
    """Liveness. Deliberately does not touch the database."""
    return {"status": "ok", "env": settings.app_env}


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    """Readiness: fails when the dependency this process cannot work without is down."""
    try:
        async with repo.get_pool().connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
        return {"status": "ready", "database": "up"}
    except Exception as exc:
        log.warning("readiness_failed", error=str(exc))
        return {"status": "degraded", "database": "down"}
