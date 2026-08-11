"""Embedding. Gemini needs its own REST call because the OpenAI shim rejects task_type."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping
from typing import Any, Literal

import httpx

from app.config import settings
from app.errors import EmbeddingFailed
from app.llm.providers import get_client
from app.llm.ratelimit import RateLimiter, limiter_for

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]

_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_MAX_BATCH = 50
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


async def embed_texts(
    texts: list[str], *, task_type: TaskType, max_retries: int = 5
) -> list[list[float]]:
    if not texts:
        return []
    if settings.embedding_provider == "gemini":
        return await _embed_gemini(texts, task_type=task_type, max_retries=max_retries)
    return await _embed_openai_compatible(texts)


async def embed_query(text: str) -> list[float]:
    vectors = await embed_texts([text], task_type="RETRIEVAL_QUERY")
    return vectors[0]


async def _embed_openai_compatible(texts: list[str]) -> list[list[float]]:
    client = get_client(settings.embedding_provider)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _MAX_BATCH):
        chunk = texts[start : start + _MAX_BATCH]
        response = await client.embeddings.create(
            model=settings.embedding_model,
            input=chunk,
            dimensions=settings.embedding_dim,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(list(item.embedding) for item in ordered)
    if len(vectors) != len(texts):
        raise EmbeddingFailed(f"expected {len(texts)} vectors, got {len(vectors)}")
    return vectors


async def _embed_gemini(
    texts: list[str], *, task_type: TaskType, max_retries: int
) -> list[list[float]]:
    if not settings.gemini_api_key:
        raise EmbeddingFailed("gemini_api_key is not configured")

    limiter = limiter_for("gemini-embeddings", settings.gemini_embed_rpm)
    url = f"{_GEMINI_BASE}/models/{settings.embedding_model}:batchEmbedContents"
    vectors: list[list[float]] = []

    async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
        for start in range(0, len(texts), _MAX_BATCH):
            chunk = texts[start : start + _MAX_BATCH]
            payload: dict[str, Any] = {
                "requests": [
                    {
                        "model": f"models/{settings.embedding_model}",
                        "content": {"parts": [{"text": text}]},
                        "taskType": task_type,
                        "outputDimensionality": settings.embedding_dim,
                    }
                    for text in chunk
                ]
            }
            vectors.extend(
                await _post_batch(client, limiter, url, payload, max_retries, cost=len(chunk))
            )

    return vectors


async def _post_batch(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    url: str,
    payload: Mapping[str, Any],
    max_retries: int,
    cost: int,
) -> list[list[float]]:
    for attempt in range(max_retries + 1):
        await limiter.acquire(cost)
        response = await client.post(
            url, headers={"x-goog-api-key": settings.gemini_api_key}, json=payload
        )
        if response.status_code == 200:
            embeddings = response.json().get("embeddings")
            if not embeddings:
                raise EmbeddingFailed(f"no embeddings in response: {response.text[:200]}")
            return [item["values"] for item in embeddings]

        if response.status_code not in _RETRYABLE_STATUS or attempt == max_retries:
            raise EmbeddingFailed(f"HTTP {response.status_code}: {response.text[:200]}")

        await asyncio.sleep(min(2.0**attempt, 8.0) + random.uniform(0, 0.5))  # noqa: S311

    raise EmbeddingFailed("exhausted retries")
