"""
session_db.py - per-user chat session persistence in Postgres.

Table: chat_sessions
  - username    : who owns the session
  - session_id  : UUID, used as the key throughout the app
  - title       : auto-set from the first question (truncated to 60 chars)
  - messages    : JSONB list of {role, content, sources?}
  - created_at / updated_at
"""
import json
import os
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / "config" / ".env", override=True)


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def ensure_table():
    """Create chat_sessions table + index if they don't exist. Safe to call on every startup."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id          SERIAL PRIMARY KEY,
                        username    TEXT NOT NULL,
                        session_id  TEXT NOT NULL UNIQUE,
                        title       TEXT NOT NULL DEFAULT 'New Chat',
                        messages    JSONB NOT NULL DEFAULT '[]',
                        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_username
                        ON chat_sessions(username);
                """)
    finally:
        conn.close()


def create_session(username: str) -> str:
    """Insert a blank session row and return the new session_id."""
    session_id = str(uuid.uuid4())
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO chat_sessions (username, session_id) VALUES (%s, %s)",
                    (username, session_id),
                )
    finally:
        conn.close()
    return session_id


def list_sessions(username: str) -> list[dict]:
    """Return all sessions for a user ordered by most recently updated."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT session_id, title, created_at, updated_at
                FROM chat_sessions
                WHERE username = %s
                ORDER BY updated_at DESC
            """, (username,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def load_messages(session_id: str) -> list[dict]:
    """Return the messages list for a session (empty list if none)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT messages FROM chat_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            return (row[0] or []) if row else []
    finally:
        conn.close()


def save_messages(session_id: str, messages: list[dict], title: str | None = None):
    """Persist messages. If title is provided, update it too."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if title:
                    cur.execute("""
                        UPDATE chat_sessions
                        SET messages = %s::jsonb, title = %s, updated_at = now()
                        WHERE session_id = %s
                    """, (json.dumps(messages), title, session_id))
                else:
                    cur.execute("""
                        UPDATE chat_sessions
                        SET messages = %s::jsonb, updated_at = now()
                        WHERE session_id = %s
                    """, (json.dumps(messages), session_id))
    finally:
        conn.close()


def delete_session(session_id: str):
    """Permanently delete a session and its messages."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM chat_sessions WHERE session_id = %s",
                    (session_id,),
                )
    finally:
        conn.close()
