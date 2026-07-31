"""Load the Bitext support corpus into resolved_cases.

uv run python scripts/load_corpus.py [--per-intent 500] [--reset]
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import httpx
import pyarrow.parquet as pq

from app.corpus import INTENT_MAP
from app.db import connect

PARQUET_URL = (
    "https://huggingface.co/api/datasets/"
    "bitext/Bitext-customer-support-llm-chatbot-training-dataset/"
    "parquet/default/train/0.parquet"
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PARQUET_PATH = DATA_DIR / "bitext.parquet"
SEED = 20260731


def download_if_missing() -> None:
    if PARQUET_PATH.exists():
        return
    DATA_DIR.mkdir(exist_ok=True)
    print(f"downloading {PARQUET_URL}")
    with httpx.stream("GET", PARQUET_URL, follow_redirects=True, timeout=120.0) as r:
        r.raise_for_status()
        with PARQUET_PATH.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    print(f"  saved {PARQUET_PATH.stat().st_size // 1024} KB")


def load_rows(per_intent: int) -> list[tuple[str, str, str]]:
    table = pq.read_table(PARQUET_PATH).to_pydict()

    # Half of Bitext carries {{Order Number}}-style templates, some malformed.
    # Dropping those rows beats inventing 391 substitutions, and leaves plenty.
    buckets: dict[str, list[tuple[str, str, str]]] = {}
    for instruction, intent, response in zip(
        table["instruction"], table["intent"], table["response"], strict=True
    ):
        if "{{" in instruction or "{{" in response:
            continue
        mapped = INTENT_MAP[intent]
        buckets.setdefault(mapped, []).append((mapped, instruction.strip(), response.strip()))

    rng = random.Random(SEED)  # noqa: S311 - seeded for a reproducible sample, not secrets
    rows: list[tuple[str, str, str]] = []
    for mapped in sorted(buckets):
        pool = buckets[mapped]
        take = min(per_intent, len(pool))
        rows.extend(rng.sample(pool, take))
        print(f"  {mapped:16s} {take:5d} of {len(pool)} clean")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-intent", type=int, default=500)
    parser.add_argument("--reset", action="store_true", help="delete existing bitext rows first")
    args = parser.parse_args()

    download_if_missing()

    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM resolved_cases WHERE source = 'bitext'")
        row = cur.fetchone()
        existing: int = row[0] if row else 0

        if existing and not args.reset:
            print(f"{existing} bitext rows already loaded; pass --reset to replace them")
            return 1
        if args.reset and existing:
            cur.execute("DELETE FROM resolved_cases WHERE source = 'bitext'")
            print(f"deleted {existing} existing bitext rows")

        rows = load_rows(args.per_intent)
        cur.executemany(
            """
            INSERT INTO resolved_cases (intent, language, customer_text, resolution_text, source)
            VALUES (%s, 'en', %s, %s, 'bitext')
            """,
            rows,
        )
        conn.commit()

    print(f"inserted {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
