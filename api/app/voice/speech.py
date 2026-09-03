"""Sarvam speech endpoints.

These are plain REST, not the OpenAI-compatible /v1 path the chat models use, so they
do not go through app.llm. Same account, same key, different host path and a different
auth header.

Sarvam also publishes WebSocket variants of both. They are not used here: the REST
calls are what the baseline measurement needs, and streaming STT only pays off once
retrieval moves onto the partial transcript.
"""

from __future__ import annotations

import base64
import re

import httpx

from app.config import settings
from app.errors import TriageError

_STT_URL = "https://api.sarvam.ai/speech-to-text"
_TTS_URL = "https://api.sarvam.ai/text-to-speech"

# A sentence end, or the fallback that keeps a rambling clause under the TTS char cap.
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


class SpeechUnavailable(TriageError):
    """The speech provider failed. Distinct from a model failure: the text path is fine."""


def _headers() -> dict[str, str]:
    if not settings.sarvam_api_key:
        raise SpeechUnavailable("sarvam_api_key is not set, so voice cannot run")
    return {"api-subscription-key": settings.sarvam_api_key}


async def transcribe(audio: bytes, *, filename: str = "turn.webm") -> tuple[str, str | None]:
    """Audio in, transcript and detected language out."""
    async with httpx.AsyncClient(timeout=settings.voice_timeout_seconds) as http:
        try:
            response = await http.post(
                _STT_URL,
                headers=_headers(),
                files={"file": (filename, audio, "application/octet-stream")},
                data={
                    "model": settings.stt_model,
                    "language_code": settings.stt_language,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SpeechUnavailable(
                f"speech-to-text failed: {exc.response.status_code} {exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SpeechUnavailable(f"speech-to-text failed: {exc}") from exc

    payload = response.json()
    return payload.get("transcript", ""), payload.get("language_code")


async def synthesize(text: str, *, language: str | None = None) -> bytes:
    """Text in, one complete WAV out.

    One WAV per call rather than a single stream, because the caller plays sentences as
    they finish and each needs its own header to be playable on arrival.
    """
    body = {
        "text": text[: settings.tts_max_chars],
        "language_code": language or settings.tts_language,
        "model": settings.tts_model,
        "speaker": settings.tts_speaker,
        "speech_sample_rate": settings.tts_sample_rate,
        "output_audio_codec": "wav",
    }
    async with httpx.AsyncClient(timeout=settings.voice_timeout_seconds) as http:
        try:
            response = await http.post(_TTS_URL, headers=_headers(), json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # The body says which model was retired or which speaker is wrong for it.
            raise SpeechUnavailable(
                f"text-to-speech failed: {exc.response.status_code} {exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SpeechUnavailable(f"text-to-speech failed: {exc}") from exc

    audios = response.json().get("audios") or []
    if not audios:
        raise SpeechUnavailable("text-to-speech returned no audio")
    return base64.b64decode(audios[0])


def sentences(chunks: str, *, min_chars: int | None = None) -> tuple[list[str], str]:
    """Split streamed text into speakable pieces, returning the unfinished tail.

    `min_chars` keeps "Hi." from becoming its own request: a very short first sentence
    costs a whole TTS round trip and buys almost no audio to play during it. It also
    delays the first sound, which is the metric this exists to move, so the default is
    a setting and the trade is measured rather than assumed.
    """
    if min_chars is None:
        min_chars = settings.tts_min_sentence_chars
    parts = _SENTENCE_END.split(chunks)
    if len(parts) == 1:
        return [], chunks

    complete, tail = parts[:-1], parts[-1]
    out: list[str] = []
    pending = ""
    for part in complete:
        pending = f"{pending} {part}".strip()
        if len(pending) >= min_chars:
            out.append(pending)
            pending = ""
    return out, f"{pending} {tail}".strip() if pending else tail
