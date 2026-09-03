from __future__ import annotations

from app.agent.prompts.classify import build_classify_prompt, build_ticket_user_message
from app.agent.schemas import Classification, classification_for
from app.config import settings
from app.domains import Domain
from app.errors import TriageError
from app.llm import CallStats, complete_json


async def classify_ticket(
    subject: str, body: str, domain: Domain
) -> tuple[Classification | None, CallStats | None, str | None]:
    """Classify one ticket against its own desk's taxonomy.

    Never raises; a failure becomes a human_review route.
    """
    try:
        classification, stats = await complete_json(
            provider=settings.classifier_provider,
            model=settings.classifier_model,
            system=build_classify_prompt(domain),
            user=build_ticket_user_message(subject, body),
            schema=classification_for(domain.intents),
            temperature=settings.classifier_temperature,
            max_tokens=settings.classifier_max_tokens,
        )
    except TriageError as exc:
        return None, None, f"classify: {exc}"
    return classification, stats, None
