from app.evals.metrics import accuracy, macro_f1, per_label_scores


def test_perfect_predictions_score_one():
    pairs = [("a", "a"), ("b", "b"), ("a", "a")]
    scores = per_label_scores(pairs, ["a", "b"])
    assert accuracy(pairs) == 1.0
    assert macro_f1(scores) == 1.0


def test_precision_and_recall_differ_when_a_label_is_over_predicted():
    # "a" is predicted three times but is correct only twice; "b" is missed once.
    pairs = [("a", "a"), ("a", "a"), ("b", "a")]
    by_label = {s.label: s for s in per_label_scores(pairs, ["a", "b"])}

    assert by_label["a"].precision == 2 / 3
    assert by_label["a"].recall == 1.0
    assert by_label["b"].precision == 0.0
    assert by_label["b"].recall == 0.0


def test_support_counts_expected_not_predicted():
    pairs = [("a", "b"), ("a", "b"), ("b", "b")]
    by_label = {s.label: s for s in per_label_scores(pairs, ["a", "b"])}
    assert by_label["a"].support == 2
    assert by_label["b"].support == 1


def test_labels_with_no_support_are_excluded_from_macro_f1():
    """An intent absent from the eval set should not drag the average to zero."""
    pairs = [("a", "a"), ("b", "b")]
    scores = per_label_scores(pairs, ["a", "b", "never_seen"])
    assert macro_f1(scores) == 1.0


def test_empty_input_is_zero_not_a_crash():
    assert accuracy([]) == 0.0
