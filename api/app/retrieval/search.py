from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.db import connect
from app.llm.embeddings import embed_query


class RetrievedCase(BaseModel):
    case_id: str
    intent: str
    language: str
    customer_text: str
    resolution_text: str
    score: float
    similarity: float
    source: str = "bitext"


class RetrievalResult(BaseModel):
    cases: list[RetrievedCase] = Field(default_factory=list)
    weak: bool = True
    # True when every case behind a draft was generated rather than resolved by a person.
    # Two of the eight intents have no real cases at all, so without this the drafter cites
    # machine-written answers and nothing downstream can tell.
    synthetic_only: bool = False
    best_similarity: float = 0.0
    method_scores: dict[str, Any] = Field(default_factory=dict)


_VECTOR_SQL = """
SELECT id::text, intent, language, customer_text, resolution_text, source,
       1 - (embedding <=> %(query)s::vector) AS similarity
FROM resolved_cases
WHERE embedding IS NOT NULL
  AND domain_id = %(domain)s
  AND (%(intent)s::text IS NULL OR intent = %(intent)s)
ORDER BY embedding <=> %(query)s::vector
LIMIT %(k)s
"""

_LEXICAL_SQL = """
SELECT id::text, intent, language, customer_text, resolution_text, source,
       ts_rank_cd(fts, websearch_to_tsquery('english', %(q)s)) AS rank
FROM resolved_cases
WHERE fts @@ websearch_to_tsquery('english', %(q)s)
  AND domain_id = %(domain)s
  AND (%(intent)s::text IS NULL OR intent = %(intent)s)
ORDER BY rank DESC
LIMIT %(k)s
"""


def reciprocal_rank_fusion(ranked_lists: dict[str, list[str]], k: int) -> dict[str, float]:
    """score(doc) = sum of 1/(k + rank) over legs. k dampens rank 1 vs rank 5."""
    scores: dict[str, float] = {}
    for ids in ranked_lists.values():
        for rank, case_id in enumerate(ids, start=1):
            scores[case_id] = scores.get(case_id, 0.0) + 1.0 / (k + rank)
    return scores


def _to_vector_literal(values: list[float]) -> str:
    return f"[{','.join(f'{v:.6f}' for v in values)}]"


def _fetch_blocking(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [c.name for c in cur.description or []]
        return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


async def _fetch(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """psycopg here is synchronous, so it runs off the loop; the API serves polls mid-run."""
    return await asyncio.to_thread(_fetch_blocking, sql, params)


async def _both_legs(
    query_vector: str, text: str, domain: str, intent: str | None, depth: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The two legs are independent, so pay for the slower one rather than their sum."""
    return await asyncio.gather(
        _fetch(
            _VECTOR_SQL, {"query": query_vector, "domain": domain, "intent": intent, "k": depth}
        ),
        _fetch(_LEXICAL_SQL, {"q": text, "domain": domain, "intent": intent, "k": depth}),
    )


async def find_similar_cases(
    *, text: str, intent: str | None, domain: str, k: int | None = None
) -> RetrievalResult:
    top_k = k or settings.retrieval_top_k
    depth = settings.retrieval_candidates

    query_vector = _to_vector_literal(await embed_query(text))

    vector_rows, lexical_rows = await _both_legs(query_vector, text, domain, intent, depth)

    # Degraded beats dead: an intent filter that matched nothing falls back to the rest of
    # the domain. Never past it. A laptop that will not boot answered from a refund policy
    # is worse than no evidence at all, because the drafter cannot tell it is in the wrong
    # business and the judge is grading groundedness rather than relevance to the desk.
    if intent is not None and not vector_rows and not lexical_rows:
        vector_rows, lexical_rows = await _both_legs(query_vector, text, domain, None, depth)

    by_id: dict[str, dict[str, Any]] = {}
    similarity: dict[str, float] = {}
    for row in vector_rows:
        by_id[row["id"]] = row
        similarity[row["id"]] = float(row["similarity"])
    for row in lexical_rows:
        by_id.setdefault(row["id"], row)

    fused = reciprocal_rank_fusion(
        {
            "vector": [r["id"] for r in vector_rows],
            "lexical": [r["id"] for r in lexical_rows],
        },
        settings.rrf_k,
    )
    if not fused:
        return RetrievalResult(cases=[], weak=True, best_similarity=0.0, method_scores={})

    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    highest = max(score for _, score in ordered)

    cases = [
        RetrievedCase(
            case_id=case_id,
            intent=by_id[case_id]["intent"],
            language=by_id[case_id]["language"],
            customer_text=by_id[case_id]["customer_text"],
            resolution_text=by_id[case_id]["resolution_text"],
            score=round(score / highest, 4) if highest else 0.0,
            similarity=round(similarity.get(case_id, 0.0), 4),
            source=by_id[case_id].get("source") or "bitext",
        )
        for case_id, score in ordered
    ]

    # Cosine, not the fused score: fusion is relative, so it stays high even on junk results.
    best_similarity = max((c.similarity for c in cases), default=0.0)

    return RetrievalResult(
        cases=cases,
        weak=best_similarity < settings.weak_retrieval_floor,
        synthetic_only=bool(cases) and all(c.source == "synthetic" for c in cases),
        best_similarity=round(best_similarity, 4),
        method_scores={
            "vector_rank": {r["id"]: i + 1 for i, r in enumerate(vector_rows)},
            "lexical_rank": {r["id"]: i + 1 for i, r in enumerate(lexical_rows)},
            "fused": {cid: round(s, 6) for cid, s in ordered},
        },
    )
