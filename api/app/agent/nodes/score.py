from __future__ import annotations

from typing import Any

from app.agent.prompts.draft import build_cases_block
from app.agent.prompts.judge import build_judge_prompt
from app.agent.schemas import JudgeScores
from app.config import settings
from app.errors import TriageError
from app.llm import CallStats, complete_json


async def score_draft(
    *,
    subject: str,
    body: str,
    intent: str,
    urgency: str,
    sentiment: str,
    cases: list[dict[str, Any]],
    draft: str,
) -> tuple[JudgeScores | None, CallStats | None, str | None]:
    try:
        scores, stats = await complete_json(
            provider=settings.judge_provider,
            model=settings.judge_model,
            system=build_judge_prompt(
                subject=subject,
                body=body,
                intent=intent,
                urgency=urgency,
                sentiment=sentiment,
                cases_block=build_cases_block(cases),
                draft=draft,
            ),
            user="Grade the draft now.",
            schema=JudgeScores,
            temperature=settings.judge_temperature,
            max_tokens=settings.judge_max_tokens,
        )
    except TriageError as exc:
        return None, None, f"score: {exc}"
    return scores, stats, None
