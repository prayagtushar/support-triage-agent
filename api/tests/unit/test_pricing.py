from app.llm.pricing import estimate_inr


def test_inr_priced_model_is_not_converted():
    # sarvam-105b: 4 INR per 1M in, 16 INR per 1M out
    assert estimate_inr("sarvam-105b", 1_000_000, 1_000_000, usd_to_inr=87.0) == 20.0


def test_usd_priced_model_is_converted():
    # gemini-3.5-flash-lite: 0.30 USD per 1M in
    assert estimate_inr("gemini-3.5-flash-lite", 1_000_000, 0, usd_to_inr=100.0) == 30.0


def test_unknown_model_returns_none_rather_than_zero():
    assert estimate_inr("some-model-we-never-priced", 1000, 1000, usd_to_inr=87.0) is None


def test_zero_tokens_costs_nothing():
    assert estimate_inr("sarvam-105b", 0, 0, usd_to_inr=87.0) == 0.0
