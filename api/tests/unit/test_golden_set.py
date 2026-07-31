import json
from collections import Counter
from pathlib import Path

import pytest

from app.corpus import TAXONOMY

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden" / "golden_v0.jsonl"

REQUIRED = {
    "id",
    "subject",
    "body",
    "expected_intent",
    "expected_urgency",
    "language",
    "expected_route",
    "notes",
}


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line]


def test_every_row_has_exactly_the_required_fields(rows):
    for row in rows:
        assert set(row) == REQUIRED, f"{row.get('id')} has {set(row) ^ REQUIRED} unexpected/missing"


def test_ids_are_unique(rows):
    duplicates = [i for i, n in Counter(r["id"] for r in rows).items() if n > 1]
    assert not duplicates


def test_labels_are_inside_their_vocabularies(rows):
    for row in rows:
        assert row["expected_intent"] in TAXONOMY, row["id"]
        assert row["expected_urgency"] in {"P1", "P2", "P3", "P4"}, row["id"]
        assert row["language"] in {"en", "hi-en", "hi"}, row["id"]
        assert row["expected_route"] in {"auto_reply", "human_review", "escalate"}, row["id"]


def test_p1_tickets_never_expect_auto_reply(rows):
    """The routing policy's hard override, asserted on the exam itself."""
    offenders = [
        r["id"]
        for r in rows
        if r["expected_urgency"] == "P1" and r["expected_route"] == "auto_reply"
    ]
    assert not offenders, f"P1 must never auto-reply: {offenders}"


def test_every_ticket_explains_its_labels(rows):
    """Future-you will not remember why a label is what it is."""
    for row in rows:
        assert len(row["notes"].strip()) > 30, row["id"]


def test_every_intent_is_represented(rows):
    counts = Counter(r["expected_intent"] for r in rows)
    missing = set(TAXONOMY) - set(counts)
    assert not missing, f"no coverage for {missing}"


def test_non_english_share_is_within_target_band(rows):
    share = sum(1 for r in rows if r["language"] != "en") / len(rows)
    assert 0.20 <= share <= 0.35, f"non-English share is {share:.0%}, target band is 25-30%"


def test_set_contains_adversarial_cases(rows):
    adversarial = [r for r in rows if r["notes"].startswith("ADVERSARIAL")]
    assert len(adversarial) >= 5
