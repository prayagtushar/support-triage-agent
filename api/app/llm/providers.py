from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from openai import AsyncOpenAI

from app.config import Provider, settings


@dataclass(frozen=True)
class ProviderConfig:
    name: Provider
    base_url: str
    api_key: str
    rpm: int
    tpm: int


def get_provider(name: Provider) -> ProviderConfig:
    match name:
        case "sarvam":
            return ProviderConfig(
                name,
                settings.sarvam_base_url,
                settings.sarvam_api_key,
                settings.sarvam_rpm,
                settings.sarvam_tpm,
            )
        case "gemini":
            return ProviderConfig(
                name,
                settings.gemini_base_url,
                settings.gemini_api_key,
                settings.gemini_rpm,
                settings.gemini_tpm,
            )
        case "groq":
            return ProviderConfig(
                name,
                settings.groq_base_url,
                settings.groq_api_key,
                settings.groq_rpm,
                settings.groq_tpm,
            )
        case "openrouter":
            return ProviderConfig(
                name,
                settings.openrouter_base_url,
                settings.openrouter_api_key,
                settings.openrouter_rpm,
                settings.openrouter_tpm,
            )


@cache
def get_client(name: Provider) -> AsyncOpenAI:
    config = get_provider(name)
    if not config.api_key:
        raise RuntimeError(f"{name} has no API key configured")
    # Retries are handled in app.llm.client so the policy is ours and the
    # attempt count reaches CallStats.
    return AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        max_retries=0,
        timeout=settings.llm_timeout_seconds,
    )
