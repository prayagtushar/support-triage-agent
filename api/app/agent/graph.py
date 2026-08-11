from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes.classify import classify_ticket
from app.agent.nodes.draft import draft_reply
from app.agent.nodes.retrieve import retrieve_cases
from app.agent.nodes.route import RouteSignals, composite_confidence, decide_route
from app.agent.nodes.score import score_draft
from app.agent.state import TriageState
from app.agent.timing import timed


@timed("classify")
async def classify_node(state: TriageState) -> dict[str, Any]:
    classification, stats, error = await classify_ticket(
        state.get("subject", ""), state.get("body", "")
    )
    update: dict[str, Any] = {
        "classification": classification.model_dump() if classification else None
    }
    if error:
        update["errors"] = [error]
    if stats:
        update["call_stats"] = [{"node": "classify", **stats.as_dict()}]
    return update


@timed("retrieve")
async def retrieve_node(state: TriageState) -> dict[str, Any]:
    classification = state.get("classification")
    intent = classification.get("intent") if classification else None

    result, error = await retrieve_cases(state.get("subject", ""), state.get("body", ""), intent)
    update: dict[str, Any] = {
        "retrieved_cases": [c.model_dump() for c in result.cases],
        "retrieval_weak": result.weak,
        "retrieval_similarity": result.best_similarity,
    }
    if error:
        update["errors"] = [error]
    return update


@timed("draft")
async def draft_node(state: TriageState) -> dict[str, Any]:
    classification = state.get("classification") or {}
    draft, stats, error = await draft_reply(
        subject=state.get("subject", ""),
        body=state.get("body", ""),
        cases=state.get("retrieved_cases", []),
        urgency=str(classification.get("urgency", "P4")),
        sentiment=str(classification.get("sentiment", "neutral")),
        retrieval_weak=bool(state.get("retrieval_weak", True)),
    )
    update: dict[str, Any] = {
        "draft": draft.reply_text if draft else None,
        "draft_citations": draft.citations if draft else [],
        "draft_is_safe_fallback": draft.is_safe_fallback if draft else False,
    }
    if error:
        update["errors"] = [error]
    if stats:
        update["call_stats"] = [{"node": "draft", **stats.as_dict()}]
    return update


@timed("score")
async def score_node(state: TriageState) -> dict[str, Any]:
    draft = state.get("draft")
    if not draft:
        return {"judge_scores": None}

    classification = state.get("classification") or {}
    scores, stats, error = await score_draft(
        subject=state.get("subject", ""),
        body=state.get("body", ""),
        intent=str(classification.get("intent", "other")),
        urgency=str(classification.get("urgency", "P4")),
        sentiment=str(classification.get("sentiment", "neutral")),
        cases=state.get("retrieved_cases", []),
        draft=draft,
    )
    update: dict[str, Any] = {"judge_scores": scores.model_dump() if scores else None}
    if error:
        update["errors"] = [error]
    if stats:
        update["call_stats"] = [{"node": "score", **stats.as_dict()}]
    return update


@timed("route")
async def route_node(state: TriageState) -> dict[str, Any]:
    signals = RouteSignals(
        classification=state.get("classification"),
        draft=state.get("draft"),
        judge=state.get("judge_scores"),
        retrieval_weak=bool(state.get("retrieval_weak", True)),
        retrieval_similarity=float(state.get("retrieval_similarity", 0.0)),
        is_safe_fallback=bool(state.get("draft_is_safe_fallback", False)),
    )
    route, reason = decide_route(signals)
    return {
        "route": route,
        "route_reason": reason,
        "composite_confidence": composite_confidence(signals),
    }


def after_classify(state: TriageState) -> str:
    """Skip the expensive nodes when there is no intent; these go to a human anyway."""
    return "route" if state.get("classification") is None else "retrieve"


def build_graph(checkpointer: Any | None = None) -> CompiledStateGraph[Any, Any, Any, Any]:
    builder = StateGraph(TriageState)
    builder.add_node("classify", classify_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("draft", draft_node)
    builder.add_node("score", score_node)
    builder.add_node("route", route_node)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify", after_classify, {"retrieve": "retrieve", "route": "route"}
    )
    builder.add_edge("retrieve", "draft")
    builder.add_edge("draft", "score")
    builder.add_edge("score", "route")
    builder.add_edge("route", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())
