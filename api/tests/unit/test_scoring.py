from app.evals.scoring import (
    auto_reply_precision,
    latency_summary,
    reliability_buckets,
    review_recall,
    sweep_thresholds,
)


def row(**kw):
    base = {
        "id": "x",
        "expected_route": "auto_reply",
        "route": "auto_reply",
        "composite_confidence": 0.9,
        "route_reason": "composite 0.90 at or above auto-reply threshold",
        "total_ms": 1000,
        "language": "en",
    }
    base.update(kw)
    return base


def test_auto_reply_precision_counts_only_what_we_actually_sent():
    rows = [
        row(),
        row(expected_route="human_review"),  # sent but should not have been
        row(route="human_review", expected_route="human_review"),  # not sent, irrelevant
    ]
    precision, correct, sent = auto_reply_precision(rows)
    assert (correct, sent) == (1, 2)
    assert precision == 0.5


def test_review_recall_treats_escalate_as_a_human_catching_it():
    """Escalate and review are different queues but both mean a human owns it."""
    rows = [
        row(expected_route="human_review", route="escalate"),
        row(expected_route="escalate", route="human_review"),
        row(expected_route="human_review", route="auto_reply"),  # missed
    ]
    _, caught, needed = review_recall(rows)
    assert (caught, needed) == (2, 3)


def test_precision_is_zero_when_nothing_was_auto_replied():
    precision, _, sent = auto_reply_precision([row(route="human_review")])
    assert (precision, sent) == (0.0, 0)


def test_reliability_buckets_report_stated_against_observed():
    rows = [
        row(composite_confidence=0.92, route="auto_reply", expected_route="auto_reply"),
        row(composite_confidence=0.95, route="auto_reply", expected_route="human_review"),
        row(composite_confidence=0.55, route="human_review", expected_route="human_review"),
    ]
    buckets = {b["lower"]: b for b in reliability_buckets(rows)}
    assert buckets[0.9]["n"] == 2
    assert buckets[0.9]["observed_correct"] == 0.5
    assert buckets[0.5]["observed_correct"] == 1.0


def test_raising_the_threshold_sends_fewer_and_should_not_lower_precision():
    rows = [
        row(composite_confidence=0.86, expected_route="human_review"),
        row(composite_confidence=0.95, expected_route="auto_reply"),
    ]
    low, high = sweep_thresholds(rows, [0.85, 0.90])
    assert low["auto_replied"] == 2
    assert high["auto_replied"] == 1
    assert high["auto_reply_precision"] > low["auto_reply_precision"]


def test_sweep_leaves_hard_rule_routes_alone():
    """P1 and weak-retrieval routes are policy, not threshold effects."""
    rows = [
        row(
            route="escalate",
            expected_route="escalate",
            composite_confidence=0.99,
            route_reason="P1 never auto-replies regardless of confidence",
        )
    ]
    for result in sweep_thresholds(rows, [0.5, 0.99]):
        assert result["routing_accuracy"] == 1.0


def test_latency_summary_reports_p95_not_just_the_mean():
    rows = [row(total_ms=ms) for ms in (100, 200, 300, 400, 10_000)]
    summary = latency_summary(rows)
    assert summary["p50_ms"] == 300
    assert summary["p95_ms"] == 10_000
    assert summary["mean_ms"] > summary["p50_ms"]
