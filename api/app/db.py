from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg

from app.config import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

_MIGRATION_LOCK_KEY = 0x5452_4147

_SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class MigrationDriftError(RuntimeError):
    """An already-applied migration file was edited after it ran."""


@contextmanager
def connect(*, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.database_url, autocommit=autocommit) as conn:
        yield conn


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def discover_migrations() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def apply_migrations(conn: psycopg.Connection) -> list[str]:
    applied: list[str] = []

    with conn.cursor() as cur:
        cur.execute(_SCHEMA_MIGRATIONS_DDL)
        cur.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_KEY,))
        cur.execute("SELECT filename, checksum FROM schema_migrations")
        recorded: dict[str, str] = dict(cur.fetchall())
    conn.commit()

    try:
        for path in discover_migrations():
            sql = path.read_text(encoding="utf-8")
            checksum = _checksum(sql)

            if path.name in recorded:
                if recorded[path.name] != checksum:
                    raise MigrationDriftError(
                        f"{path.name} was modified after it was applied. "
                        "Add a new migration instead."
                    )
                continue

            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
            conn.commit()
            applied.append(path.name)
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_KEY,))
        conn.commit()

    return applied
