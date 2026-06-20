"""
obs_db.py - Query observability: logging every RAG inference call and
providing aggregated stats for the Observability dashboard.

Table: query_logs
"""
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / "config" / ".env", override=True)


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


# -- Schema ---------------------------------------------------------------------

def ensure_obs_tables():
    """Create query_logs and ragas_scores tables idempotently."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS query_logs (
                        id              SERIAL PRIMARY KEY,
                        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
                        username        TEXT,
                        session_id      TEXT,
                        app_filter      TEXT,
                        comparison_mode BOOLEAN     NOT NULL DEFAULT false,
                        source_filter   TEXT,
                        question        TEXT        NOT NULL,
                        answer_text     TEXT,
                        context_chunks  JSONB,
                        chunks_returned INT         NOT NULL DEFAULT 0,
                        top_score       FLOAT,
                        avg_score       FLOAT,
                        retrieve_ms     INT         NOT NULL DEFAULT 0,
                        generate_ms     INT         NOT NULL DEFAULT 0,
                        total_ms        INT         NOT NULL DEFAULT 0,
                        input_tokens    INT         NOT NULL DEFAULT 0,
                        output_tokens   INT         NOT NULL DEFAULT 0,
                        error           TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_ql_created
                        ON query_logs(created_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_ql_username
                        ON query_logs(username);
                    CREATE INDEX IF NOT EXISTS idx_ql_error
                        ON query_logs(error) WHERE error IS NOT NULL;

                    -- RAGAs evaluation scores (one row per evaluated query)
                    CREATE TABLE IF NOT EXISTS ragas_scores (
                        id               SERIAL PRIMARY KEY,
                        query_log_id     INT         NOT NULL REFERENCES query_logs(id),
                        evaluated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                        faithfulness     FLOAT,
                        answer_relevancy FLOAT,
                        context_precision FLOAT,
                        eval_model       TEXT        NOT NULL DEFAULT 'claude-haiku-4-5',
                        error            TEXT
                    );
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_ragas_query_log_id
                        ON ragas_scores(query_log_id);
                    CREATE INDEX IF NOT EXISTS idx_ragas_evaluated_at
                        ON ragas_scores(evaluated_at DESC);

                    -- Add answer_text / context_chunks columns to existing installs
                    ALTER TABLE query_logs
                        ADD COLUMN IF NOT EXISTS answer_text    TEXT,
                        ADD COLUMN IF NOT EXISTS context_chunks JSONB;
                """)
    finally:
        conn.close()


# -- Write ----------------------------------------------------------------------

def log_query(
    username: str,
    session_id: str,
    question: str,
    app_filter,
    comparison_mode: bool,
    source_filter,
    chunks_returned: int,
    top_score,
    avg_score,
    retrieve_ms: int,
    generate_ms: int,
    input_tokens: int,
    output_tokens: int,
    error=None,
    answer_text=None,
    context_chunks=None,   # list of dicts: {source, app_name, content, score}
) -> int | None:
    """Insert one row into query_logs. Returns the new id, or None on error.
    Errors are swallowed - never break UX."""
    import json
    try:
        conn = _get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    ctx_json = json.dumps(context_chunks) if context_chunks else None
                    cur.execute("""
                        INSERT INTO query_logs (
                            username, session_id, question,
                            answer_text, context_chunks,
                            app_filter, comparison_mode, source_filter,
                            chunks_returned, top_score, avg_score,
                            retrieve_ms, generate_ms, total_ms,
                            input_tokens, output_tokens, error
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING id
                    """, (
                        username, session_id, question[:500],
                        answer_text, ctx_json,
                        app_filter, comparison_mode, source_filter,
                        chunks_returned, top_score, avg_score,
                        retrieve_ms, generate_ms, retrieve_ms + generate_ms,
                        input_tokens, output_tokens,
                        error[:500] if error else None,
                    ))
                    return cur.fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None   # never let observability logging crash the app


# -- Read - aggregated stats ----------------------------------------------------

def get_kpi_stats() -> dict:
    """Return summary KPIs: today/7d/total counts, latency, errors, tokens."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*)                                                         AS total_queries,
                    COUNT(*) FILTER (WHERE created_at >= now() - INTERVAL '7 days') AS queries_7d,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE)              AS queries_today,
                    ROUND(AVG(total_ms) FILTER (
                        WHERE error IS NULL
                          AND created_at >= now() - INTERVAL '7 days'
                    ))::INT                                                          AS avg_latency_ms,
                    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_ms)
                        FILTER (
                            WHERE error IS NULL
                              AND created_at >= now() - INTERVAL '7 days'
                        ))::INT                                                      AS p95_latency_ms,
                    COUNT(*) FILTER (
                        WHERE error IS NOT NULL
                          AND created_at >= now() - INTERVAL '7 days'
                    )                                                                AS errors_7d,
                    COALESCE(SUM(input_tokens + output_tokens)
                        FILTER (WHERE created_at >= CURRENT_DATE), 0)               AS tokens_today,
                    COALESCE(SUM(input_tokens + output_tokens)
                        FILTER (WHERE created_at >= now() - INTERVAL '7 days'), 0)  AS tokens_7d
                FROM query_logs
            """)
            row = cur.fetchone()
            keys = [
                "total_queries", "queries_7d", "queries_today",
                "avg_latency_ms", "p95_latency_ms", "errors_7d",
                "tokens_today", "tokens_7d",
            ]
            return dict(zip(keys, row)) if row else {k: 0 for k in keys}
    finally:
        conn.close()


def get_daily_volume(days: int = 14) -> list[dict]:
    """Return per-day query counts (success + error) for the last N days."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC')              AS day,
                    COUNT(*)                                         AS queries,
                    COUNT(*) FILTER (WHERE error IS NOT NULL)        AS errors
                FROM query_logs
                WHERE created_at >= now() - (%(d)s || ' days')::INTERVAL
                GROUP BY 1
                ORDER BY 1
            """, {"d": str(days)})
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_latency_trend(days: int = 7) -> list[dict]:
    """Return per-day avg latency breakdown (retrieve vs generate)."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    ROUND(AVG(retrieve_ms))::INT        AS avg_retrieve_ms,
                    ROUND(AVG(generate_ms))::INT        AS avg_generate_ms,
                    ROUND(AVG(total_ms))::INT           AS avg_total_ms
                FROM query_logs
                WHERE error IS NULL
                  AND created_at >= now() - (%(d)s || ' days')::INTERVAL
                GROUP BY 1
                ORDER BY 1
            """, {"d": str(days)})
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_app_distribution() -> list[dict]:
    """Return query counts grouped by effective app target."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    CASE
                        WHEN comparison_mode      THEN 'Comparison'
                        WHEN app_filter IS NULL   THEN 'All Apps'
                        ELSE app_filter
                    END  AS app_label,
                    COUNT(*) AS queries
                FROM query_logs
                GROUP BY 1
                ORDER BY 2 DESC
            """)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_token_trend(days: int = 7) -> list[dict]:
    """Return per-day token totals (input + output)."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    COALESCE(SUM(input_tokens),  0)     AS input_tokens,
                    COALESCE(SUM(output_tokens), 0)     AS output_tokens
                FROM query_logs
                WHERE created_at >= now() - (%(d)s || ' days')::INTERVAL
                GROUP BY 1
                ORDER BY 1
            """, {"d": str(days)})
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_recent_queries(limit: int = 50) -> list[dict]:
    """Return the most recent query log rows for the query table."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    id, created_at, username,
                    app_filter, comparison_mode, source_filter,
                    LEFT(question, 120)            AS question,
                    chunks_returned,
                    ROUND(top_score::numeric, 3)   AS top_score,
                    total_ms, retrieve_ms, generate_ms,
                    input_tokens, output_tokens,
                    error
                FROM query_logs
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_recent_errors(limit: int = 20) -> list[dict]:
    """Return the most recent failed queries."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, created_at, username,
                       LEFT(question, 120) AS question, error
                FROM query_logs
                WHERE error IS NOT NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# -- RAGAs helpers --------------------------------------------------------------

def get_unevaluated_queries(limit: int = 20) -> list[dict]:
    """Return queries that have answer+context stored but no RAGAs score yet."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ql.id, ql.question, ql.answer_text, ql.context_chunks
                FROM query_logs ql
                LEFT JOIN ragas_scores rs ON rs.query_log_id = ql.id
                WHERE ql.error IS NULL
                  AND ql.answer_text IS NOT NULL
                  AND ql.context_chunks IS NOT NULL
                  AND rs.id IS NULL
                ORDER BY ql.created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def save_ragas_score(
    query_log_id: int,
    faithfulness: float | None,
    answer_relevancy: float | None,
    context_precision: float | None,
    eval_model: str,
    error: str | None = None,
):
    """Upsert a RAGAs score row for a query."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ragas_scores
                        (query_log_id, faithfulness, answer_relevancy,
                         context_precision, eval_model, error)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (query_log_id) DO UPDATE SET
                        faithfulness      = EXCLUDED.faithfulness,
                        answer_relevancy  = EXCLUDED.answer_relevancy,
                        context_precision = EXCLUDED.context_precision,
                        eval_model        = EXCLUDED.eval_model,
                        evaluated_at      = now(),
                        error             = EXCLUDED.error
                """, (query_log_id, faithfulness, answer_relevancy,
                      context_precision, eval_model, error))
    finally:
        conn.close()


def get_ragas_trend(days: int = 7) -> list[dict]:
    """Return per-day average RAGAs scores."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    DATE(rs.evaluated_at AT TIME ZONE 'UTC')    AS day,
                    ROUND(AVG(rs.faithfulness)::numeric, 3)     AS avg_faithfulness,
                    ROUND(AVG(rs.answer_relevancy)::numeric, 3) AS avg_answer_relevancy,
                    ROUND(AVG(rs.context_precision)::numeric,3) AS avg_context_precision,
                    COUNT(*)                                     AS evaluated_count
                FROM ragas_scores rs
                WHERE rs.error IS NULL
                  AND rs.evaluated_at >= now() - (%(d)s || ' days')::INTERVAL
                GROUP BY 1
                ORDER BY 1
            """, {"d": str(days)})
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_ragas_kpis() -> dict:
    """Return overall average RAGAs scores (last 7 days)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ROUND(AVG(faithfulness)::numeric, 3)      AS avg_faithfulness,
                    ROUND(AVG(answer_relevancy)::numeric, 3)  AS avg_answer_relevancy,
                    ROUND(AVG(context_precision)::numeric, 3) AS avg_context_precision,
                    COUNT(*)                                   AS total_evaluated,
                    COUNT(*) FILTER (WHERE error IS NOT NULL) AS eval_errors
                FROM ragas_scores
                WHERE evaluated_at >= now() - INTERVAL '7 days'
            """)
            row = cur.fetchone()
            keys = ["avg_faithfulness", "avg_answer_relevancy",
                    "avg_context_precision", "total_evaluated", "eval_errors"]
            return dict(zip(keys, row)) if row else {k: None for k in keys}
    finally:
        conn.close()


def get_low_scoring_queries(threshold: float = 0.5, limit: int = 20) -> list[dict]:
    """Return queries where any RAGAs metric fell below threshold."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    ql.id, ql.created_at, ql.username,
                    LEFT(ql.question, 120) AS question,
                    rs.faithfulness, rs.answer_relevancy, rs.context_precision,
                    rs.evaluated_at
                FROM ragas_scores rs
                JOIN query_logs ql ON ql.id = rs.query_log_id
                WHERE rs.error IS NULL
                  AND (
                    rs.faithfulness      < %(t)s
                    OR rs.answer_relevancy  < %(t)s
                    OR rs.context_precision < %(t)s
                  )
                ORDER BY rs.evaluated_at DESC
                LIMIT %(l)s
            """, {"t": threshold, "l": limit})
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
