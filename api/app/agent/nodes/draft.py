from __future__ import annotations

from typing import Any

from app.agent.prompts.draft import build_draft_prompt
from app.agent.schemas import Draft
from app.config import settings
from app.errors import TriageError
from app.llm import CallStats, complete_json


async def draft_reply(
    *,
    subject: str,
    body: str,
    cases: list[dict[str, Any]],
    urgency: str,
    sentiment: str,
    retrieval_weak: bool,
) -> tuple[Draft | None, CallStats | None, str | None]:
    try:
        draft, stats = await complete_json(
            provider=settings.drafter_provider,
            model=settings.drafter_model,
            system=build_draft_prompt(
                cases=cases,
                subject=subject,
                body=body,
                urgency=urgency,
                sentiment=sentiment,
                retrieval_weak=retrieval_weak,
            ),
            user="Write the reply now.",
            schema=Draft,
            temperature=settings.drafter_temperature,
            max_tokens=settings.drafter_max_tokens,
        )
    except TriageError as exc:
        return None, None, f"draft: {exc}"

    # A citation past the end of the evidence renders as a broken expander in the review UI.
    valid = [c for c in draft.citations if 1 <= c <= len(cases)]
    if valid != draft.citations:
        draft = draft.model_copy(update={"citations": valid})

    return draft, stats, None
