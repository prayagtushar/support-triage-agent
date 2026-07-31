"""List-price token rates. Verified 2026-07-31; update rate and date together."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Rate:
    input_per_1m: float
    output_per_1m: float
    currency: Literal["INR", "USD"]


RATES: dict[str, Rate] = {
    "sarvam-105b": Rate(4.0, 16.0, "INR"),
    "sarvam-30b": Rate(2.5, 10.0, "INR"),
    "llama-3.3-70b-versatile": Rate(0.59, 0.79, "USD"),
    "meta-llama/llama-3.3-70b-instruct": Rate(0.13, 0.40, "USD"),
    "gemini-3.5-flash-lite": Rate(0.30, 2.50, "USD"),
    "google/gemini-2.5-flash-lite": Rate(0.10, 0.40, "USD"),
    "gemini-3.6-flash": Rate(1.50, 7.50, "USD"),
    "gemini-embedding-001": Rate(0.15, 0.0, "USD"),
    "openai/text-embedding-3-small": Rate(0.02, 0.0, "USD"),
}


def estimate_inr(
    model: str, prompt_tokens: int, completion_tokens: int, usd_to_inr: float
) -> float | None:
    """None when the model is not in the table: an unpriced call is not a free one."""
    rate = RATES.get(model)
    if rate is None:
        return None

    cost = (prompt_tokens / 1_000_000) * rate.input_per_1m + (
        completion_tokens / 1_000_000
    ) * rate.output_per_1m
    if rate.currency == "USD":
        cost *= usd_to_inr
    return round(cost, 6)
