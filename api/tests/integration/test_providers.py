"""Live provider checks. Run with: uv run pytest -m integration"""

import pytest
from pydantic import BaseModel

from app.config import settings
from app.llm import complete_json, complete_text
from app.llm.embeddings import embed_texts

pytestmark = pytest.mark.integration


class Answer(BaseModel):
    answer: str
    confident: bool


@pytest.mark.parametrize(
    ("provider", "model"),
    [
        (settings.classifier_provider, settings.classifier_model),
        (settings.judge_provider, settings.judge_model),
        (settings.drafter_provider, settings.drafter_model),
    ],
)
async def test_each_configured_model_returns_valid_json(provider, model):
    parsed, stats = await complete_json(
        provider=provider,
        model=model,
        system="You answer trivia. Set confident to true when certain.",
        user="What is the capital of France? Put the city in 'answer'.",
        schema=Answer,
        max_tokens=2048,
    )

    assert "paris" in parsed.answer.lower()
    assert stats.prompt_tokens > 0
    assert stats.estimated_cost_inr is not None, f"{model} is missing from the pricing table"


async def test_drafter_produces_hinglish():
    text, _ = await complete_text(
        provider=settings.drafter_provider,
        model=settings.drafter_model,
        system="Reply in natural Hinglish (romanized Hindi mixed with English), one sentence.",
        user="Customer asks: refund kab milega?",
        temperature=0.3,
        max_tokens=settings.drafter_max_tokens,
    )
    assert len(text.strip()) > 0


async def test_document_and_query_embeddings_differ_and_match_configured_dim():
    docs = await embed_texts(["refund kab milega"], task_type="RETRIEVAL_DOCUMENT")
    queries = await embed_texts(["refund kab milega"], task_type="RETRIEVAL_QUERY")

    assert len(docs[0]) == settings.embedding_dim
    assert len(queries[0]) == settings.embedding_dim
    # Asymmetric embedding is the whole reason this bypasses the compat layer.
    assert docs[0] != queries[0]
