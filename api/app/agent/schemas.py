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
    # Self-reported, and weakly calibrated at best. Kept as one signal among
    # several; M8 measures how much it is actually worth.
    confidence: float = Field(ge=0.0, le=1.0)
    # For the review UI and debugging, not chain of thought. Capped so we are
    # not paying for an essay per ticket.
    rationale: str = Field(max_length=280)


class Draft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reply_text: str
    citations: list[int] = Field(default_factory=list)
    used_language: Literal["en", "hi-en", "hi"]
    is_safe_fallback: bool


class JudgeScores(BaseModel):
    model_config = ConfigDict(extra="ignore")

    # Integer 1-5, not 0-100: a model cannot meaningfully separate 82 from 87,
    # and pretending it can only adds noise to the routing thresholds.
    groundedness: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    tone: int = Field(ge=1, le=5)
    notes: str = Field(max_length=400)
