"""
Apply the v3 hybrid-retrieval migration (idempotent).

Executes each statement in migrate_v3_hybrid.sql separately so an unsupported
optional index (e.g. HNSW on older pgvector) is logged and skipped rather than
aborting the whole migration.

Usage:
    python infrastructure/scripts/migrate_v3.py
"""
import logging
import os
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / "config" / ".env", override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

SQL_FILE = Path(__file__).with_name("migrate_v3_hybrid.sql")


def split_statements(sql: str) -> list[str]:
    # Strip line comments, then split on semicolons.
    no_comments = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    return [s.strip() for s in re.split(r";\s*\n", no_comments) if s.strip()]


def main() -> None:
    db_url = os.environ.get("DATABASE_ADMIN_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        log.error("DATABASE_ADMIN_URL / DATABASE_URL not set.")
        sys.exit(1)

    statements = split_statements(SQL_FILE.read_text(encoding="utf-8"))
    log.info("Applying %d statements from %s", len(statements), SQL_FILE.name)

    conn = psycopg2.connect(db_url)
    conn.autocommit = True  # each DDL stands alone; continue past optional failures
    ok = failed = 0
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                label = " ".join(stmt.split())[:70]
                try:
                    cur.execute(stmt)
                    ok += 1
                    log.info("  OK   %s", label)
                except Exception as exc:
                    failed += 1
                    log.warning("  SKIP %s  (%s)", label, exc)
    finally:
        conn.close()

    log.info("Migration done: %d ok, %d skipped.", ok, failed)


if __name__ == "__main__":
    main()
