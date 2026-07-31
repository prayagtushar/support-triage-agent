"""Embed resolved cases that do not yet have a vector.

    uv run python scripts/embed_corpus.py [--batch 100]

Resumable: it only claims rows where embedding IS NULL, so a rate-limit
failure part-way through costs the current batch and nothing else. Re-running
picks up whatever is left, including rows whose text was edited afterwards.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.config import settings
from app.db import connect
from app.errors import EmbeddingFailed
from app.llm.embeddings import embed_texts


def pending_count() -> int:
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM resolved_cases WHERE embedding IS NULL")
        row = cur.fetchone()
        return row[0] if row else 0


def claim_batch(size: int) -> list[tuple[str, str]]:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id::text, customer_text FROM resolved_cases "
            "WHERE embedding IS NULL ORDER BY id LIMIT %s",
            (size,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def store(ids: list[str], vectors: list[list[float]]) -> None:
    payload = [
        (f"[{','.join(f'{v:.6f}' for v in vec)}]", case_id)
        for case_id, vec in zip(ids, vectors, strict=True)
    ]
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            "UPDATE resolved_cases SET embedding = %s::vector WHERE id = %s::uuid",
            payload,
        )
        conn.commit()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=100)
    args = parser.parse_args()

    total = pending_count()
    if total == 0:
        print("every case already has an embedding")
        return 0

    print(f"embedding {total} cases with {settings.embedding_model} at {settings.embedding_dim}d")
    done = 0

    while True:
        batch = claim_batch(args.batch)
        if not batch:
            break

        ids = [case_id for case_id, _ in batch]
        texts = [text for _, text in batch]
        try:
            vectors = await embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")
        except EmbeddingFailed as exc:
            print(f"  failed after {done}/{total}: {exc}")
            print("  re-run to resume from here")
            return 1

        store(ids, vectors)
        done += len(batch)
        print(f"  {done}/{total}")

    print(f"embedded {done} cases")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
