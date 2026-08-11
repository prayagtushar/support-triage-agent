from __future__ import annotations

from app.agent.prompts.classify import build_classify_prompt, build_ticket_user_message
from app.agent.schemas import Classification
from app.config import settings
from app.errors import TriageError
from app.llm import CallStats, complete_json


async def classify_ticket(
    subject: str, body: str
) -> tuple[Classification | None, CallStats | None, str | None]:
    """Classify one ticket. Never raises; a failure becomes a human_review route."""
    try:
        classification, stats = await complete_json(
            provider=settings.classifier_provider,
            model=settings.classifier_model,
            system=build_classify_prompt(),
            user=build_ticket_user_message(subject, body),
            schema=Classification,
            temperature=settings.classifier_temperature,
            max_tokens=settings.classifier_max_tokens,
        )
    except TriageError as exc:
        return None, None, f"classify: {exc}"
    return classification, stats, None
