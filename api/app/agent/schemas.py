from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Intent = Literal[
    "billing",
    "refund",
    "account_access",
    "bug_report",
    "how_to",
    "shipping",
    "feature_request",
    "other",
]
Urgency = Literal["P1", "P2", "P3", "P4"]
Language = Literal["en", "hi-en", "hi", "unknown"]
Sentiment = Literal["angry", "frustrated", "neutral", "positive"]
Route = Literal["auto_reply", "human_review", "escalate"]


class Classification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: Intent
    urgency: Urgency
    language: Language
    sentiment: Sentiment
    # Self-reported and weakly calibrated; one signal among several.
    confidence: float = Field(ge=0.0, le=1.0)
    # For the review UI, not chain of thought. Capped so we don't pay for an essay per ticket.
    rationale: str = Field(max_length=280)


class Draft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reply_text: str
    citations: list[int] = Field(default_factory=list)
    used_language: Literal["en", "hi-en", "hi"]
    is_safe_fallback: bool


class JudgeScores(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # 1-5, not 0-100: a model cannot separate 82 from 87, and pretending otherwise adds noise.
    groundedness: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    tone: int = Field(ge=1, le=5)
    notes: str = Field(max_length=400)
