from __future__ import annotations

from operator import add
from typing import Annotated, Any

from typing_extensions import TypedDict


class TriageState(TypedDict, total=False):
    ticket_id: str
    subject: str
    body: str
    channel: str

    classification: dict[str, Any] | None

    retrieved_cases: list[dict[str, Any]]
    retrieval_weak: bool
    retrieval_similarity: float

    draft: str | None
    draft_citations: list[int]
    draft_is_safe_fallback: bool

    judge_scores: dict[str, Any] | None
    composite_confidence: float | None

    route: str | None
    route_reason: str | None

    # Append rather than replace, so no node can erase another node's report.
    errors: Annotated[list[str], add]
    node_timings_ms: Annotated[list[dict[str, Any]], add]
    call_stats: Annotated[list[dict[str, Any]], add]
