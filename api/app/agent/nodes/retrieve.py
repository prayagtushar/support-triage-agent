from __future__ import annotations

from app.errors import TriageError
from app.retrieval.search import RetrievalResult, find_similar_cases


async def retrieve_cases(
    subject: str, body: str, intent: str | None
) -> tuple[RetrievalResult, str | None]:
    """Never raises. A retrieval failure is just weak retrieval, which downstream nodes handle."""
    try:
        result = await find_similar_cases(text=f"{subject}\n{body}", intent=intent)
    except (TriageError, OSError) as exc:
        return RetrievalResult(cases=[], weak=True, best_similarity=0.0), f"retrieve: {exc}"
    return result, None
