"""Apply pending migrations. Idempotent."""

from __future__ import annotations

import sys

from app.config import settings
from app.db import apply_migrations, connect


def main() -> int:
    print(f"migrating {settings.database_url.rsplit('@', 1)[-1]}")

    with connect() as conn:
        applied = apply_migrations(conn)

    if applied:
        for name in applied:
            print(f"  applied {name}")
        print(f"{len(applied)} migration(s) applied")
    else:
        print("  nothing to apply, schema is current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
