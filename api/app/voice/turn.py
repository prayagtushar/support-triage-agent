"""One voice turn, timed at every boundary.

The metric this project exists to move is `first_audio_ms`: the gap between the caller
finishing their sentence and the first sound coming back. Everything else here is
either producing that number or explaining it.
"""

from __future__ import annotations

import base64
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

import structlog

from app.agent.graph import build_graph, build_voice_graph, route_node, score_node
from app.agent.nodes.draft import draft_reply
from app.agent.prompts.draft import build_draft_prompt
from app.config import settings
from app.domains import get as get_domain
from app.errors import TriageError
from app.llm import stream_text
from app.voice.speech import sentences, synthesize, transcribe

log = structlog.get_logger()

# Appended to the drafting prompt on the streamed path. The JSON schema cannot be
# streamed: nothing is speakable until the object closes, which is the entire reply.
_PROSE_ONLY = (
    "\n\nOUTPUT FORMAT OVERRIDE: this reply will be spoken aloud, not read. Return the "
    "reply text only, as plain prose. No JSON, no markdown, no citation markers, no "
    "bullet points. Keep it under four sentences."
)


@dataclass
class TurnTimings:
    """Milliseconds from the moment the caller stopped speaking."""

    arm: str
    transcript_ms: int | None = None
    retrieved_ms: int | None = None
    first_token_ms: int | None = None
    first_audio_ms: int | None = None
    reply_complete_ms: int | None = None
    judged_ms: int | None = None
    audio_chunks: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _arm() -> str:
    if settings.voice_fast_drafter:
        return "fast_drafter"
    if settings.voice_stream_draft:
        return "stream_draft"
    if settings.voice_judge_async:
        return "judge_async"
    return "baseline"


def _drafter() -> tuple[str, str, int]:
    """Which model writes the spoken reply, and how much room it gets."""
    if settings.voice_fast_drafter:
        return (
            settings.voice_drafter_provider,
            settings.voice_drafter_model,
            settings.voice_drafter_max_tokens,
        )
    return settings.drafter_provider, settings.drafter_model, settings.drafter_max_tokens


async def _speak(text: str, language: str | None) -> dict[str, Any]:
    audio = await synthesize(text, language=language)
    return {"type": "audio", "wav_b64": base64.b64encode(audio).decode(), "text": text}


async def _stream_draft_audio(
    state: dict[str, Any], language: str | None, timings: TurnTimings, t0: float
) -> AsyncIterator[dict[str, Any]]:
    """Draft and speak at the same time: TTS each sentence while the model writes the next."""
    classification = state.get("classification") or {}
    domain = await get_domain(state["domain_id"])
    provider, model, max_tokens = _drafter()
    stream = stream_text(
        provider=provider,  # type: ignore[arg-type]
        model=model,
        system=build_draft_prompt(
            cases=state.get("retrieved_cases", []),
            subject=state.get("subject", ""),
            body=state.get("body", ""),
            urgency=str(classification.get("urgency", "P4")),
            sentiment=str(classification.get("sentiment", "neutral")),
            retrieval_weak=bool(state.get("retrieval_weak", True)),
            domain=domain.description,
        )
        + _PROSE_ONLY,
        user="Write the reply now.",
        temperature=settings.drafter_temperature,
        max_tokens=max_tokens,
    )

    buffered = ""
    async for piece in stream:
        buffered += piece
        if timings.first_token_ms is None:
            timings.first_token_ms = int((time.monotonic() - t0) * 1000)
        ready, buffered = sentences(buffered)
        for sentence in ready:
            yield await _speak(sentence, language)
            if timings.first_audio_ms is None:
                timings.first_audio_ms = int((time.monotonic() - t0) * 1000)
            timings.audio_chunks += 1

    if buffered.strip():
        yield await _speak(buffered.strip(), language)
        if timings.first_audio_ms is None:
            timings.first_audio_ms = int((time.monotonic() - t0) * 1000)
        timings.audio_chunks += 1

    state["draft"] = stream.text
    # Streaming buys latency and costs structure. The schema fields the drafter would
    # have returned are gone, so the router loses the drafter's own fallback signal and
    # the reviewer loses inline citations. The evidence is still recorded; which
    # sentence leaned on which case is not.
    state["draft_citations"] = []
    state["draft_is_safe_fallback"] = False
    if stream.stats:
        state.setdefault("call_stats", []).append({"node": "draft", **stream.stats.as_dict()})


async def run_voice_turn(
    audio: bytes, *, ticket_id: str, domain_id: str
) -> AsyncIterator[dict[str, Any]]:
    """Yields transcript, then audio as it is produced, then the finished turn."""
    t0 = time.monotonic()
    timings = TurnTimings(arm=_arm())

    def elapsed() -> int:
        return int((time.monotonic() - t0) * 1000)

    try:
        transcript, language = await transcribe(audio)
    except TriageError as exc:
        yield {"type": "error", "message": str(exc)}
        return

    timings.transcript_ms = elapsed()
    if not transcript.strip():
        yield {"type": "error", "message": "nothing was said"}
        return
    yield {"type": "transcript", "text": transcript, "language": language}

    seed: dict[str, Any] = {
        "ticket_id": ticket_id,
        "domain_id": domain_id,
        "subject": transcript[:120],
        "body": transcript,
        "channel": "voice",
    }
    config: Any = {"configurable": {"thread_id": ticket_id}}

    if timings.arm == "baseline":
        # The text pipeline exactly as it ships, with a microphone bolted on. Judge
        # inline, reply spoken only once every node has finished. This is the number
        # the rest of the work has to beat.
        final = dict(await build_graph().ainvoke(seed, config=config))
        timings.reply_complete_ms = timings.judged_ms = elapsed()
        reply = final.get("draft")
        if reply:
            yield await _speak(reply, language)
            timings.first_audio_ms = elapsed()
            timings.audio_chunks = 1
    else:
        state = dict(await build_voice_graph().ainvoke(seed, config=config))
        timings.retrieved_ms = elapsed()

        if settings.voice_stream_draft:
            async for event in _stream_draft_audio(state, language, timings, t0):
                yield event
            timings.reply_complete_ms = elapsed()
        else:
            draft, stats, error = await draft_reply(
                domain=(await get_domain(state["domain_id"])).description,
                subject=state.get("subject", ""),
                body=state.get("body", ""),
                cases=state.get("retrieved_cases", []),
                urgency=str((state.get("classification") or {}).get("urgency", "P4")),
                sentiment=str((state.get("classification") or {}).get("sentiment", "neutral")),
                retrieval_weak=bool(state.get("retrieval_weak", True)),
            )
            state["draft"] = draft.reply_text if draft else None
            state["draft_citations"] = draft.citations if draft else []
            state["draft_is_safe_fallback"] = bool(draft and draft.is_safe_fallback)
            if error:
                timings.errors.append(error)
            if stats:
                state.setdefault("call_stats", []).append({"node": "draft", **stats.as_dict()})
            timings.reply_complete_ms = elapsed()
            if state["draft"]:
                yield await _speak(state["draft"], language)
                timings.first_audio_ms = elapsed()
                timings.audio_chunks = 1

        # The caller has already heard the reply. The judge still runs, still logs, and
        # still decides whether a human sees this turn. It just no longer stands between
        # the question and the answer.
        state.update(await score_node(state))  # type: ignore[arg-type]
        state.update(await route_node(state))  # type: ignore[arg-type]
        timings.judged_ms = elapsed()
        final = state

    timings.errors.extend(final.get("errors", []))
    log.info("voice_turn", ticket_id=ticket_id, **timings.as_dict())
    yield {
        "type": "done",
        "timings": timings.as_dict(),
        "transcript": transcript,
        # The graph's own state, unrenamed, so the row written from it cannot disagree
        # with the screen rendered from it.
        "state": dict(final),
    }


__all__ = ["TurnTimings", "run_voice_turn"]
