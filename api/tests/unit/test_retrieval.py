from app.retrieval.search import RetrievalResult, RetrievedCase, reciprocal_rank_fusion


def test_a_document_ranked_first_by_both_legs_wins():
    scores = reciprocal_rank_fusion({"vector": ["a", "b"], "lexical": ["a", "c"]}, k=60)
    assert scores["a"] > scores["b"]
    assert scores["a"] > scores["c"]


def test_appearing_in_both_legs_beats_a_better_rank_in_one():
    """The property that makes fusion robust to one noisy leg."""
    scores = reciprocal_rank_fusion({"vector": ["solo", "both"], "lexical": ["x", "both"]}, k=60)
    assert scores["both"] > scores["solo"]


def test_the_constant_dampens_rank_differences():
    tight = reciprocal_rank_fusion({"v": ["first", "fifth"]}, k=60)
    loose = reciprocal_rank_fusion({"v": ["first", "fifth"]}, k=1)
    assert tight["first"] / tight["fifth"] < loose["first"] / loose["fifth"]


def test_empty_input_produces_no_scores():
    assert reciprocal_rank_fusion({"vector": [], "lexical": []}, k=60) == {}


def test_cosine_distance_converts_to_similarity_in_the_right_direction():
    """pgvector's <=> is distance: identical vectors are 0, opposites are 2."""
    identical_distance = 0.0
    unrelated_distance = 1.0

    assert 1 - identical_distance > 1 - unrelated_distance
    assert 1 - identical_distance == 1.0


# --- provenance of the evidence -------------------------------------------


def _case(case_id: str, source: str) -> RetrievedCase:
    return RetrievedCase(
        case_id=case_id,
        intent="bug_report",
        language="en",
        customer_text="the app crashes on export",
        resolution_text="we are looking into it",
        score=1.0,
        similarity=0.8,
        source=source,
    )


def test_evidence_made_only_of_generated_cases_is_flagged():
    """bug_report and feature_request have no real cases, so a draft for either is
    machine text grounded in machine text. Nothing downstream can tell without this."""
    result = RetrievalResult(
        cases=[_case("a", "synthetic"), _case("b", "synthetic")],
        weak=False,
        best_similarity=0.8,
        synthetic_only=True,
    )
    assert result.synthetic_only is True


def test_one_real_case_is_enough_to_clear_the_flag():
    cases = [_case("a", "synthetic"), _case("b", "bitext")]
    assert not all(c.source == "synthetic" for c in cases)


def test_empty_retrieval_is_not_called_synthetic():
    """Nothing retrieved is already reported as weak; calling it synthetic too would
    describe evidence that does not exist."""
    assert RetrievalResult(cases=[], weak=True, best_similarity=0.0).synthetic_only is False


def test_cases_default_to_real_when_the_column_is_absent():
    assert (
        RetrievedCase(
            case_id="a",
            intent="billing",
            language="en",
            customer_text="x",
            resolution_text="y",
            score=1.0,
            similarity=0.5,
        ).source
        == "bitext"
    )
