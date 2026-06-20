"""
pipeline_db.py - DB helpers for pipeline run tracking and schedule management.

Tables created on first use:
  pipeline_runs      - log of every pipeline execution
  pipeline_schedules - per-source schedule config (weekly by default)
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / "config" / ".env", override=True)

SOURCES = ["google_play", "app_store", "news", "web_pages", "youtube"]


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


# -- Schema setup -------------------------------------------------------------

def ensure_pipeline_tables():
    """Create pipeline tracking tables + seed schedule rows. Idempotent."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_runs (
                        id            SERIAL PRIMARY KEY,
                        source        TEXT        NOT NULL,
                        status        TEXT        NOT NULL DEFAULT 'running',
                        started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                        finished_at   TIMESTAMPTZ,
                        chunks_before INT         NOT NULL DEFAULT 0,
                        chunks_after  INT         NOT NULL DEFAULT 0,
                        chunks_added  INT         NOT NULL DEFAULT 0,
                        log_output    TEXT        NOT NULL DEFAULT ''
                    );
                    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_source
                        ON pipeline_runs(source);
                    CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started
                        ON pipeline_runs(started_at DESC);

                    CREATE TABLE IF NOT EXISTS pipeline_schedules (
                        source        TEXT PRIMARY KEY,
                        enabled       BOOLEAN     NOT NULL DEFAULT false,
                        interval_days INT         NOT NULL DEFAULT 7,
                        last_run_at   TIMESTAMPTZ,
                        next_run_at   TIMESTAMPTZ
                    );
                """)
                # Seed one row per source if missing
                for src in SOURCES:
                    cur.execute("""
                        INSERT INTO pipeline_schedules (source, enabled, interval_days)
                        VALUES (%s, false, 7)
                        ON CONFLICT (source) DO NOTHING
                    """, (src,))
    finally:
        conn.close()


# -- Chunk counts -------------------------------------------------------------

def get_source_chunk_counts() -> dict[str, int]:
    """Return {source: count} for all sources."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT source, COUNT(*) FROM document_chunks GROUP BY source")
            return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def get_source_chunk_count(source: str) -> int:
    """Return chunk count for a single source."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM document_chunks WHERE source = %s", (source,)
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_total_chunk_count() -> int:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks")
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_chunks_by_app_source() -> list[dict]:
    """Return chunk counts grouped by (app_name, source)."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT app_name, source, COUNT(*) AS count
                FROM document_chunks
                GROUP BY app_name, source
                ORDER BY app_name, source
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# -- Run logging ---------------------------------------------------------------

def log_run_start(source: str, chunks_before: int) -> int:
    """Insert a 'running' pipeline_runs row. Returns the new run id."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs (source, status, chunks_before)
                    VALUES (%s, 'running', %s) RETURNING id
                """, (source, chunks_before))
                return cur.fetchone()[0]
    finally:
        conn.close()


def log_run_finish(run_id: int, status: str, chunks_after: int, log_output: str):
    """Update a pipeline_runs row when the job completes or errors."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE pipeline_runs
                    SET status       = %s,
                        finished_at  = now(),
                        chunks_after = %s,
                        chunks_added = %s - chunks_before,
                        log_output   = %s
                    WHERE id = %s
                """, (status, chunks_after, chunks_after, log_output[:20000], run_id))
    finally:
        conn.close()


def get_run_history(limit: int = 40) -> list[dict]:
    """Return the most recent pipeline runs."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id, source, status,
                    started_at, finished_at,
                    chunks_added, log_output,
                    EXTRACT(EPOCH FROM
                        (COALESCE(finished_at, now()) - started_at)
                    )::INT AS duration_secs
                FROM pipeline_runs
                ORDER BY started_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_last_run(source: str) -> dict | None:
    """Return the most recent completed run for a source."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, status, started_at, finished_at, chunks_added
                FROM pipeline_runs
                WHERE source = %s AND status IN ('done', 'error')
                ORDER BY started_at DESC LIMIT 1
            """, (source,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_running_sources() -> list[str]:
    """Return sources that currently have an active (running) job."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT source FROM pipeline_runs
                WHERE status = 'running'
                  AND started_at > now() - INTERVAL '30 minutes'
            """)
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


# -- Schedules -----------------------------------------------------------------

def get_schedules() -> list[dict]:
    """Return schedule config for all sources."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT source, enabled, interval_days, last_run_at, next_run_at
                FROM pipeline_schedules
                ORDER BY source
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_schedule(source: str, enabled: bool):
    """
    Enable or disable the weekly schedule for a source.
    When enabling: sets next_run_at = now + 7 days if not already set.
    When disabling: clears next_run_at.
    """
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if enabled:
                    cur.execute("""
                        UPDATE pipeline_schedules
                        SET enabled = true,
                            next_run_at = COALESCE(
                                next_run_at,
                                now() + INTERVAL '7 days'
                            )
                        WHERE source = %s
                    """, (source,))
                else:
                    cur.execute("""
                        UPDATE pipeline_schedules
                        SET enabled = false, next_run_at = NULL
                        WHERE source = %s
                    """, (source,))
    finally:
        conn.close()


def mark_schedule_ran(source: str):
    """After a successful scheduled run, update last_run_at and advance next_run_at by 7 days."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE pipeline_schedules
                    SET last_run_at = now(),
                        next_run_at = now() + (interval_days * INTERVAL '1 day')
                    WHERE source = %s
                """, (source,))
    finally:
        conn.close()


def get_overdue_sources() -> list[str]:
    """Return enabled sources whose next_run_at has passed."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source FROM pipeline_schedules
                WHERE enabled = true
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= now()
            """)
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
