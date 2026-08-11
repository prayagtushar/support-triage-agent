from app.retrieval.search import reciprocal_rank_fusion


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
