"""Minimal, transparent migration runner: applies migrations/NNN_*.sql in order, each in its own
transaction, and records it in schema_migrations. Safe to run repeatedly (already-applied files
are skipped). Run inside the api container:  python -m placewise.migrate
"""
import sys
from pathlib import Path

import psycopg

from .config import get_settings

MIGRATIONS = Path(__file__).parent / "migrations"


def migrate(database_url: str | None = None) -> list[str]:
    url = database_url or get_settings().database_url
    applied_now: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        # One runner at a time (e.g. api and worker starting together)
        conn.execute("SELECT pg_advisory_lock(727001)")
        try:
            done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql")):
                if path.stem in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,))
                applied_now.append(path.stem)
        finally:
            conn.execute("SELECT pg_advisory_unlock(727001)")
    return applied_now


if __name__ == "__main__":
    applied = migrate()
    print("applied:", ", ".join(applied) if applied else "nothing (up to date)")
    sys.exit(0)
