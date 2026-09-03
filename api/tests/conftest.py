"""Shared fixtures.

The offline suite has no database, and the domain registry now reads one. Rather than
patch it in every file, seed the cache here with the two desks the migrations create, so
a unit test gets a working taxonomy without a connection and the API surface behaves the
way it does in production.
"""

from __future__ import annotations

import pytest

from app import domains

ECOM = domains.Domain(
    id="ecom",
    name="Consumer e-commerce",
    description="a consumer online shopping service",
    provenance="real",
    intents=(
        "account_access",
        "billing",
        "bug_report",
        "feature_request",
        "how_to",
        "other",
        "refund",
        "shipping",
    ),
    intent_labels={"billing": "billing", "refund": "refund"},
    intent_definitions={"billing": "charges and invoices."},
    classify_guidance="BOUNDARIES: none for tests.",
    classify_examples="EXAMPLE 1\nSubject: x\nBody: y\nOutput:\n{}",
)

TECH = domains.Domain(
    id="tech",
    name="Tech support desk",
    description="a consumer software and devices support desk",
    provenance="synthetic",
    intents=(
        "account_access",
        "feature_request",
        "hardware",
        "how_to",
        "other",
        "outage",
        "performance",
        "software_bug",
    ),
    intent_labels={"outage": "outage", "hardware": "hardware"},
    intent_definitions={"outage": "the service is down."},
    classify_guidance="BOUNDARIES: none for tests.",
    classify_examples="EXAMPLE 1\nSubject: x\nBody: y\nOutput:\n{}",
)


@pytest.fixture(autouse=True)
def seeded_domains():
    """Populate the registry cache so `domains.load()` never reaches for a pool."""
    domains._cache.clear()
    domains._cache.update({"ecom": ECOM, "tech": TECH})
    yield
    domains._cache.clear()
