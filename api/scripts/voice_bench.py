"""Voice latency benchmark. Runs the golden set through the voice path, one arm at a time.

    uv run python scripts/voice_bench.py --arms baseline,judge_async,stream_draft

The headline is time to first audio: the gap between the caller finishing their
sentence and the first sound coming back. Everything else is here to explain it.

Two deliberate choices, both of which cost time and both of which the number is
worthless without:

Serially, never concurrently. The provider rate limiters are per-process, so running
tickets in parallel makes them queue behind each other and the wait lands inside the
measurement. `make eval` can be concurrent because it measures quality. This cannot.

Spoken by a machine, not a person. Each golden body is synthesised once and cached, so
the audio is identical across arms and the comparison is fair. It is also cleaner than
any real caller on a real line, so every latency here is a floor.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import repo
from app.agent.checkpoint import close_checkpointer
from app.config import settings
from app.evals.golden import load_golden
from app.evals.scoring import accuracy_of, latency_summary
from app.voice.speech import SpeechUnavailable, synthesize
from app.voice.turn import run_voice_turn

ARMS = {
    # (voice_judge_async, voice_stream_draft, voice_fast_drafter)
    "baseline": (False, False, False),
    "judge_async": (True, False, False),
    "stream_draft": (True, True, False),
    "fast_drafter": (True, True, True),
}

VOICE_DIR = Path(__file__).resolve().parent.parent / "evals" / "voice"
AUDIO_DIR = VOICE_DIR / "audio"


async def build_audio(tickets: list[Any]) -> dict[str, bytes]:
    """Synthesise each ticket body once and keep it. Cached, so this is free after day one."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    clips: dict[str, bytes] = {}
    for ticket in tickets:
        path = AUDIO_DIR / f"{ticket.id}.wav"
        if path.exists():
            clips[ticket.id] = path.read_bytes()
            continue
        print(f"  synthesising {ticket.id}", flush=True)
        try:
            audio = await synthesize(ticket.body)
        except SpeechUnavailable as exc:
            print(f"  {ticket.id} failed: {exc}", file=sys.stderr)
            continue
        path.write_bytes(audio)
        clips[ticket.id] = audio
    return clips


async def run_arm(arm: str, tickets: list[Any], clips: dict[str, bytes]) -> list[dict[str, Any]]:
    judge_async, stream_draft, fast_drafter = ARMS[arm]
    settings.voice_judge_async = judge_async
    settings.voice_stream_draft = stream_draft
    settings.voice_fast_drafter = fast_drafter

    rows: list[dict[str, Any]] = []
    for index, ticket in enumerate(tickets, start=1):
        audio = clips.get(ticket.id)
        if audio is None:
            continue

        timings: dict[str, Any] = {}
        state: dict[str, Any] = {}
        transcript = ""
        failure: str | None = None
        try:
            async for event in run_voice_turn(audio, ticket_id=ticket.id, domain_id="ecom"):
                if event["type"] == "transcript":
                    transcript = event["text"]
                elif event["type"] == "error":
                    failure = event["message"]
                elif event["type"] == "done":
                    timings, state = event["timings"], event["state"]
        except Exception as exc:
            # One bad ticket must not end a 45-minute run.
            failure = f"{type(exc).__name__}: {exc}"

        classification = state.get("classification") or {}
        rows.append(
            {
                "id": ticket.id,
                "arm": arm,
                "fatal": failure is not None,
                "error": failure,
                "expected_intent": ticket.expected_intent,
                "intent": classification.get("intent"),
                "transcript": transcript,
                "reference": ticket.body,
                "route": state.get("route"),
                "expected_route": ticket.expected_route,
                # latency_summary reads total_ms, and the total that matters here is
                # the one the caller actually experiences.
                "total_ms": timings.get("first_audio_ms"),
                **{k: v for k, v in timings.items() if k.endswith("_ms")},
                "audio_chunks": timings.get("audio_chunks", 0),
            }
        )
        print(
            f"  [{arm} {index}/{len(tickets)}] {ticket.id} "
            f"first_audio={timings.get('first_audio_ms')}ms",
            flush=True,
        )
    return rows


def summarise(arm: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [r for r in rows if not r["fatal"] and r.get("total_ms")]
    stage = {}
    for field in ("transcript_ms", "retrieved_ms", "first_token_ms", "reply_complete_ms"):
        values = [{"total_ms": r[field]} for r in usable if r.get(field)]
        stage[field] = latency_summary(values)["p50_ms"] if values else None

    return {
        "arm": arm,
        "n": len(rows),
        "fatal": sum(1 for r in rows if r["fatal"]),
        "time_to_first_audio": latency_summary(usable),
        "stage_p50_ms": stage,
        # Speech recognition sits upstream of every model in the pipeline, so a drop
        # here is a transcription problem wearing a classifier's clothes.
        "intent_accuracy": round(accuracy_of(usable, "expected_intent", "intent"), 3),
        "route_agreement": round(accuracy_of(usable, "expected_route", "route"), 3),
    }


def render(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "| Arm | n | TTFA p50 | TTFA p95 | Intent acc | Route agreement |",
        "|---|---|---|---|---|---|",
    ]
    for s in summaries:
        ttfa = s["time_to_first_audio"]
        lines.append(
            f"| {s['arm']} | {s['n'] - s['fatal']} | {ttfa['p50_ms'] / 1000:.1f}s | "
            f"{ttfa['p95_ms'] / 1000:.1f}s | {s['intent_accuracy']:.3f} | "
            f"{s['route_agreement']:.3f} |"
        )
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arms", default="baseline,judge_async,stream_draft,fast_drafter")
    parser.add_argument("--golden", default="v0")
    parser.add_argument("--limit", type=int, default=0, help="sample the golden set")
    parser.add_argument("--audio-only", action="store_true", help="build the clips and stop")
    args = parser.parse_args()

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in arms if a not in ARMS]
    if unknown:
        print(f"unknown arms: {unknown}. known: {list(ARMS)}", file=sys.stderr)
        return 2

    tickets = load_golden(args.golden)
    if args.limit:
        tickets = tickets[: args.limit]

    print(f"building audio for {len(tickets)} tickets")
    clips = await build_audio(tickets)
    print(f"{len(clips)} clips ready")
    if args.audio_only:
        return 0

    await repo.open_pool()
    started = time.monotonic()
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    try:
        for arm in arms:
            print(f"\narm: {arm}")
            arm_rows = await run_arm(arm, tickets, clips)
            rows.extend(arm_rows)
            summaries.append(summarise(arm, arm_rows))
    finally:
        await close_checkpointer()
        await repo.close_pool()

    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "golden": args.golden,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "speech": {
            "stt": settings.stt_model,
            "tts": f"{settings.tts_model}/{settings.tts_speaker}",
            "note": "prompts synthesised, not spoken by a person: these latencies are a floor",
        },
        "models": {
            "classifier": f"{settings.classifier_provider}/{settings.classifier_model}",
            "drafter": f"{settings.drafter_provider}/{settings.drafter_model}",
            "judge": f"{settings.judge_provider}/{settings.judge_model}",
        },
        "arms": summaries,
        "rows": rows,
    }

    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = VOICE_DIR / f"voice_{stamp}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (VOICE_DIR / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\n{render(summaries)}\n\nwrote {path}")
    return 0


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(asyncio.run(main()))
