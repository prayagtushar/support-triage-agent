import pytest

from app.agent.nodes.route import RouteSignals, composite_confidence, decide_route
from app.config import Settings

CFG = Settings(
    route_auto_reply_threshold=0.85,
    route_review_threshold=0.55,
    composite_weight_judge=0.5,
    composite_weight_classifier=0.3,
    composite_weight_retrieval=0.2,
)


def signals(**overrides):
    base = dict(
        classification={"urgency": "P3", "confidence": 0.9, "intent": "billing"},
        draft="Here is your answer.",
        judge={"groundedness": 5, "completeness": 5, "tone": 5},
        retrieval_weak=False,
        retrieval_similarity=0.8,
        is_safe_fallback=False,
    )
    base.update(overrides)
    return RouteSignals(**base)


def test_healthy_high_confidence_ticket_auto_replies():
    route, reason = decide_route(signals(), CFG)
    assert route == "auto_reply"
    assert "auto-reply threshold" in reason


@pytest.mark.parametrize("missing", ["classification", "draft", "judge"])
def test_any_missing_upstream_output_goes_to_review(missing):
    route, reason = decide_route(signals(**{missing: None}), CFG)
    assert route == "human_review"
    assert "pipeline failure" in reason


def test_p1_escalates_even_at_perfect_confidence():
    """Blast radius, not model quality. This rule must beat every score."""
    route, reason = decide_route(
        signals(classification={"urgency": "P1", "confidence": 1.0, "intent": "bug_report"}), CFG
    )
    assert route == "escalate"
    assert "P1" in reason


def test_p1_beats_weak_retrieval_too():
    route, _ = decide_route(
        signals(
            classification={"urgency": "P1", "confidence": 1.0, "intent": "bug_report"},
            retrieval_weak=True,
        ),
        CFG,
    )
    assert route == "escalate"


def test_weak_retrieval_forces_review_despite_perfect_judge_scores():
    route, reason = decide_route(signals(retrieval_weak=True), CFG)
    assert route == "human_review"
    assert "insufficient evidence" in reason


def test_safe_fallback_forces_review():
    """A good fallback scores high on groundedness because it claims nothing.
    The router, not the judge, is what keeps it away from a customer."""
    route, _ = decide_route(signals(is_safe_fallback=True), CFG)
    assert route == "human_review"


def test_confidence_exactly_at_the_auto_reply_threshold_auto_replies():
    s = signals(
        judge={"groundedness": 5, "completeness": 5, "tone": 5},
        classification={"urgency": "P3", "confidence": 0.5, "intent": "billing"},
        retrieval_similarity=1.0,
    )
    assert composite_confidence(s, CFG) == pytest.approx(0.85)
    assert decide_route(s, CFG)[0] == "auto_reply"


def test_just_below_the_auto_reply_threshold_goes_to_review():
    s = signals(
        judge={"groundedness": 5, "completeness": 5, "tone": 5},
        classification={"urgency": "P3", "confidence": 0.49, "intent": "billing"},
        retrieval_similarity=1.0,
    )
    assert composite_confidence(s, CFG) < 0.85
    assert decide_route(s, CFG)[0] == "human_review"


def test_confidence_exactly_at_the_review_threshold_stays_in_review():
    # 0.5*(12/15) + 0.3*0.5 + 0.2*0.0 = 0.40 + 0.15 = 0.55
    s = signals(
        judge={"groundedness": 4, "completeness": 4, "tone": 4},
        classification={"urgency": "P3", "confidence": 0.5, "intent": "billing"},
        retrieval_similarity=0.0,
    )
    assert composite_confidence(s, CFG) == pytest.approx(0.55)
    assert decide_route(s, CFG)[0] == "human_review"


def test_below_the_review_floor_escalates():
    s = signals(
        judge={"groundedness": 1, "completeness": 1, "tone": 1},
        classification={"urgency": "P4", "confidence": 0.1, "intent": "other"},
        retrieval_similarity=0.1,
    )
    assert decide_route(s, CFG)[0] == "escalate"


def test_composite_is_the_documented_weighted_sum():
    s = signals(
        judge={"groundedness": 3, "completeness": 3, "tone": 3},
        classification={"urgency": "P3", "confidence": 0.5, "intent": "billing"},
        retrieval_similarity=0.5,
    )
    # 0.5*(9/15) + 0.3*0.5 + 0.2*0.5 = 0.3 + 0.15 + 0.1
    assert composite_confidence(s, CFG) == pytest.approx(0.55)


def test_composite_is_zero_when_signals_are_missing():
    assert composite_confidence(signals(judge=None), CFG) == 0.0
    assert composite_confidence(signals(classification=None), CFG) == 0.0


def test_a_missing_classifier_confidence_is_treated_as_zero_not_a_crash():
    s = signals(classification={"urgency": "P3", "intent": "billing"})
    assert composite_confidence(s, CFG) == pytest.approx(0.5 * 1.0 + 0.2 * 0.8)


def test_thresholds_come_from_config_so_policy_changes_without_code():
    strict = Settings(
        route_auto_reply_threshold=0.99,
        route_review_threshold=0.55,
        composite_weight_judge=0.5,
        composite_weight_classifier=0.3,
        composite_weight_retrieval=0.2,
    )
    assert decide_route(signals(), CFG)[0] == "auto_reply"
    assert decide_route(signals(), strict)[0] == "human_review"


def test_every_route_carries_a_human_readable_reason():
    for s in (
        signals(),
        signals(draft=None),
        signals(classification={"urgency": "P1", "confidence": 1.0, "intent": "bug_report"}),
        signals(retrieval_weak=True),
        signals(judge={"groundedness": 1, "completeness": 1, "tone": 1}, retrieval_similarity=0.0),
    ):
        _, reason = decide_route(s, CFG)
        assert len(reason) > 10
