"""The judge ablation is only as trustworthy as its reconstruction step.

`signals_of` rebuilds the router's inputs from a recorded eval row. If it drifts
from what the pipeline actually stored, the ablation silently measures the drift
instead of the judge. The script's own fidelity check catches that at runtime;
these tests catch it in CI, without needing a report on disk.
"""

from __future__ import annotations

import pytest

from app.agent.nodes.route import composite_confidence, decide_route
from scripts.ablate_judge import ARMS, arm_settings, signals_of

POLICY = {"auto_reply": 0.90, "review": 0.55, "weak_retrieval_floor": 0.40}


def row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": "g001",
        "intent": "billing",
        "urgency": "P3",
        "classifier_confidence": 0.9,
        "retrieval_weak": False,
        "retrieval_similarity": 0.7,
        "draft": "here is your answer",
        "is_safe_fallback": False,
        "judge_scores": {"groundedness": 5, "completeness": 5, "tone": 5},
        "expected_route": "auto_reply",
        "route": "auto_reply",
    }
    return {**base, **overrides}


def test_signals_carry_the_five_router_inputs():
    signals = signals_of(row())
    assert signals.classification == {"confidence": 0.9, "urgency": "P3"}
    assert signals.judge == {"groundedness": 5, "completeness": 5, "tone": 5}
    assert signals.retrieval_weak is False
    assert signals.retrieval_similarity == 0.7
    assert signals.is_safe_fallback is False


def test_failed_classification_reconstructs_as_none():
    """A ticket that never classified must not become a confident one.

    The row still has a classifier_confidence key, so defaulting rather than
    checking intent would invent a classification the pipeline never produced.
    """
    signals = signals_of(row(intent=None, classifier_confidence=None))
    assert signals.classification is None
    assert decide_route(signals, arm_settings(ARMS["full"], 0.90, POLICY))[0] == "human_review"


def test_missing_similarity_does_not_crash_the_composite():
    signals = signals_of(row(retrieval_similarity=None))
    assert signals.retrieval_similarity == 0.0


def test_arm_weights_must_sum_to_one():
    with pytest.raises(SystemExit):
        arm_settings((0.5, 0.5, 0.5), 0.90, POLICY)


@pytest.mark.parametrize("name", list(ARMS))
def test_every_arm_is_a_valid_policy(name: str):
    config = arm_settings(ARMS[name], 0.90, POLICY)
    total = (
        config.composite_weight_judge
        + config.composite_weight_classifier
        + config.composite_weight_retrieval
    )
    assert total == pytest.approx(1.0)


def test_arm_settings_uses_report_policy_not_current_config():
    """Replaying an old report under today's thresholds is the bug that made the
    fidelity check fail on report_v1, which was measured at 0.85."""
    config = arm_settings(ARMS["full"], 0.85, {**POLICY, "review": 0.50})
    assert config.route_auto_reply_threshold == 0.85
    assert config.route_review_threshold == 0.50


def test_no_judge_arm_zeroes_the_judge_contribution():
    signals = signals_of(row())
    full = composite_confidence(signals, arm_settings(ARMS["full"], 0.90, POLICY))
    no_judge = composite_confidence(signals, arm_settings(ARMS["no_judge"], 0.90, POLICY))

    # Perfect judge (15/15) and imperfect retrieval (0.7), so dropping the judge
    # must lower the composite. Equality would mean the weight never applied.
    assert full > no_judge


def test_judge_only_arm_is_exactly_the_normalised_judge_score():
    signals = signals_of(row(judge_scores={"groundedness": 3, "completeness": 3, "tone": 3}))
    assert composite_confidence(signals, arm_settings(ARMS["judge_only"], 0.90, POLICY)) == 9 / 15


def test_hard_rules_are_identical_across_arms():
    """P1, weak retrieval and safe fallback fire before the composite, so no
    reweighting can move those tickets. This is why the script reports how many
    tickets the composite actually decides."""
    for signals in (
        signals_of(row(urgency="P1")),
        signals_of(row(retrieval_weak=True)),
        signals_of(row(is_safe_fallback=True)),
    ):
        routes = {
            name: decide_route(signals, arm_settings(weights, 0.90, POLICY))[0]
            for name, weights in ARMS.items()
        }
        assert len(set(routes.values())) == 1, routes
