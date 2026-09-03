"""The desks this deployment serves.

Domain used to be one string in settings, interpolated into two prompts. It is now a
row, because a second desk needs its own corpus, its own intent taxonomy and its own
worked examples, and none of those are settings.

Loaded once and cached. Domains change when someone writes a migration, not while the
process is running, and every node on the hot path needs one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from app import repo

log = structlog.get_logger()


@dataclass(frozen=True)
class Domain:
    id: str
    name: str
    description: str
    # 'real' or 'synthetic'. Carried all the way to the UI rather than kept in a footnote:
    # a desk grounded in generated text cannot support the claims one grounded in real
    # transcripts can, and the person reading a draft should be told which they are in.
    provenance: str
    intents: tuple[str, ...]
    intent_labels: dict[str, str] = field(default_factory=dict)
    intent_definitions: dict[str, str] = field(default_factory=dict)
    classify_guidance: str = ""
    classify_examples: str = ""

    @property
    def is_synthetic(self) -> bool:
        return self.provenance == "synthetic"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "provenance": self.provenance,
            "intents": list(self.intents),
            "intent_labels": self.intent_labels,
        }


_cache: dict[str, Domain] = {}


async def load(force: bool = False) -> dict[str, Domain]:
    if _cache and not force:
        return _cache

    rows = await repo.list_domains()
    loaded: dict[str, Domain] = {}
    for row in rows:
        intents = tuple(i["intent"] for i in row["intents"])
        loaded[row["id"]] = Domain(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            provenance=row["provenance"],
            intents=intents,
            intent_labels={i["intent"]: i["label"] for i in row["intents"]},
            intent_definitions={i["intent"]: i["definition"] for i in row["intents"]},
            classify_guidance=row["classify_guidance"],
            classify_examples=row["classify_examples"],
        )

    _cache.clear()
    _cache.update(loaded)
    log.info(
        "domains_loaded",
        domains=list(loaded),
        counts={k: len(v.intents) for k, v in loaded.items()},
    )
    return _cache


async def get(domain_id: str) -> Domain:
    domains = await load()
    if domain_id not in domains:
        raise UnknownDomain(domain_id, tuple(domains))
    return domains[domain_id]


async def default_id() -> str:
    """The desk a caller lands on when they name none. First by sort order."""
    domains = await load()
    return next(iter(domains))


class UnknownDomain(ValueError):
    def __init__(self, given: str, known: tuple[str, ...]) -> None:
        super().__init__(f"unknown domain {given!r}; known: {', '.join(known)}")
        self.given = given
        self.known = known
