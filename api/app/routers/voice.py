from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import repo
from app.config import settings
from app.domains import UnknownDomain
from app.domains import default_id as default_domain
from app.domains import get as get_domain
from app.observability import flush
from app.voice.turn import arm_name, run_voice_turn

log = structlog.get_logger()
router = APIRouter(tags=["voice"])

# One turn of speech. Past this the caller is dictating, not asking, and the transcript
# costs more than it is worth.
MAX_AUDIO_BYTES = 5 * 1024 * 1024


@router.get("/voice/config")
async def voice_config() -> dict[str, Any]:
    """What the browser needs to know, and which arm is in force. Read-only."""
    return {
        # From the same function the turn uses. This was a second copy of the rule and
        # it had gone stale: it never learned the fast_drafter arm, so the page named
        # one arm while the pipeline ran another.
        "arm": arm_name(),
        "stt_model": settings.stt_model,
        "tts_model": settings.tts_model,
        "tts_speaker": settings.tts_speaker,
        "sample_rate": settings.tts_sample_rate,
        "max_audio_bytes": MAX_AUDIO_BYTES,
        "enabled": settings.voice_enabled and bool(settings.sarvam_api_key),
    }


@router.websocket("/voice/ws")
async def voice_ws(socket: WebSocket, domain: str | None = None) -> None:
    """One socket, one turn: send an audio blob, receive transcript, audio, then timings.

    A socket rather than POST because the point is to deliver the first sentence of
    audio before the last one exists. A 202-and-poll shape, which is right for text
    triage, would hide exactly the interval being measured.
    """
    await socket.accept()

    # Refused before the browser records anything, so nobody is asked for a microphone
    # to reach an error. GET /voice/config says the same thing, and the page reads it.
    if not (settings.voice_enabled and settings.sarvam_api_key):
        await socket.send_json(
            {"type": "error", "message": "Speech is switched off on this deployment."}
        )
        await socket.close()
        return

    try:
        audio = await socket.receive_bytes()
    except WebSocketDisconnect:
        return

    if len(audio) > MAX_AUDIO_BYTES:
        await socket.send_json({"type": "error", "message": "audio too long"})
        await socket.close()
        return

    used = await repo.count_tickets_last_24h()
    if used >= settings.max_tickets_per_day:
        await socket.send_json({"type": "error", "message": "daily demo limit reached"})
        await socket.close()
        return

    domain_id = domain or await default_domain()
    try:
        await get_domain(domain_id)
    except UnknownDomain as exc:
        await socket.send_json({"type": "error", "message": str(exc)})
        await socket.close()
        return

    ticket_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(ticket_id=ticket_id, domain_id=domain_id)
    try:
        async for event in run_voice_turn(audio, ticket_id=ticket_id, domain_id=domain_id):
            await socket.send_json(event)
            if event["type"] != "done":
                continue
            # Persist only once the turn is finished, so a caller who hangs up mid-answer
            # does not leave a ticket stuck at 'received' the way the text path can.
            await _persist(ticket_id, domain_id, event)
    except WebSocketDisconnect:
        log.info("voice_caller_left")
    except Exception as exc:
        log.exception("voice_turn_failed", error=str(exc))
        # An empty speech account is a billing state, not a crash, and the raw
        # HTTPStatusError repr told a visitor nothing they could act on. It is the one
        # failure here that is expected to happen eventually, so it gets a sentence.
        detail = str(exc)
        message = (
            "Speech credit has run out on this deployment. The measurements below are "
            "what it did while it was funded."
            if "402" in detail or "credit" in detail.lower()
            else f"{type(exc).__name__}: {exc}"
        )
        try:
            await socket.send_json({"type": "error", "message": message})
        except (WebSocketDisconnect, RuntimeError):
            pass
    finally:
        flush()
        structlog.contextvars.clear_contextvars()
        try:
            await socket.close()
        except RuntimeError:
            pass


ROUTE_TO_STATUS = {
    "auto_reply": "auto_replied",
    "human_review": "in_review",
    "escalate": "escalated",
}


async def _persist(ticket_id: str, domain_id: str, event: dict[str, Any]) -> None:
    """Write the turn once it is finished.

    The text path inserts the ticket first and fills the run in later, which is right
    when a background worker owns the job. Here the socket owns it, so a caller who
    hangs up mid-answer should leave nothing rather than a ticket stuck at 'received'.
    """
    transcript = event.get("transcript", "")
    state = event.get("state", {})
    await repo.insert_ticket(
        ticket_id=ticket_id,
        subject=transcript[:120] or "voice turn",
        body=transcript,
        channel="voice",
        customer_meta={"voice_timings_ms": event.get("timings", {})},
        external_ref=None,
        domain_id=domain_id,
    )
    await repo.insert_run(ticket_id, state, None)
    route = str(state.get("route") or "human_review")
    await repo.update_ticket_status(ticket_id, ROUTE_TO_STATUS.get(route, "in_review"))
