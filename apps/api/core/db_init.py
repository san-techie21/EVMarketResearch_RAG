"""Ensure the document_chunks schema exists. Runs on API startup so a fresh
cloud Postgres (Render/Neon/Supabase) self-initializes - no manual SQL step.
Idempotent and best-effort: failures (e.g. HNSW on old pgvector) are logged,
not fatal."""
import logging
import os
import re
from pathlib import Path

import psycopg2

log = logging.getLogger("voltaic.db_init")

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "infra" / "db" / "01_init.sql"


def ensure_schema() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not SCHEMA_SQL.exists():
        return
    sql = "\n".join(
        line for line in SCHEMA_SQL.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--")
    )
    statements = [s.strip() for s in re.split(r";\s*\n", sql) if s.strip()]
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
    except Exception as exc:
        log.warning("ensure_schema: cannot connect yet (%s)", exc)
        return
    try:
        with conn.cursor() as cur:
            for stmt in statements:
                try:
                    cur.execute(stmt)
                except Exception as exc:
                    log.warning("ensure_schema: skipped a statement (%s)", exc)
        log.info("ensure_schema: schema verified.")
    finally:
        conn.close()
