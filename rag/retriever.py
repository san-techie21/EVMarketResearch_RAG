"""
Shared retrieval + generation logic used by both the FastAPI and Streamlit apps.
"""
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / "config" / ".env", override=True)

# sentence_transformers must load before psycopg2 on Windows (DLL conflict)
sys.path.insert(0, str(Path(__file__).parents[1] / "pipeline"))
from processing.embedder import embed_texts

import anthropic
import psycopg2
import psycopg2.extras

_anthropic = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL  = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
TOP_K  = int(os.environ.get("TOP_K", 12))

SYSTEM_PROMPT = """\
You are a competitive intelligence analyst for a smart energy app research team.
Your knowledge base covers two categories of North American apps:

EV CHARGING APPS (category: ev_charging):
  ChargePoint, EVgo, Blink, PlugShare, Electrify America, FLO, EVCS, Shell Recharge, Tesla

PROSUMER / HOME ENERGY APPS (category: prosumer):
  Tesla Powerwall, Enphase Enlighten, SolarEdge mySolarEdge, Emporia Energy,
  Sense, SunPower, Generac PWRview, Span

Content sources per app:
  - google_play / app_store : user reviews
  - news                    : press coverage and articles
  - web_pages               : official website content
  - youtube                 : video summaries and tutorials

Answer questions using ONLY the provided context chunks.
Each chunk is tagged with source type, app name, and category.
Distinguish between user sentiment (reviews), company claims (web), and demonstrations (video).
Be specific, cite apps by name, highlight cross-app and cross-category comparisons when relevant.
If the context is insufficient, say so rather than guessing."""


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


ALL_EV_APPS = [
    "chargepoint", "evgo", "blink", "plugshare",
    "electrify_america", "flo", "evcs", "shell_recharge", "tesla",
]

ALL_PROSUMER_APPS = [
    "tesla_powerwall", "enphase", "solaredge", "emporia",
    "sense", "sunpower", "generac", "span",
]

ALL_APPS = ALL_EV_APPS + ALL_PROSUMER_APPS


_YT_KEYWORDS = {"youtube", "transcript", "video", "tutorial", "demo", "watch"}


def retrieve(question: str, app_filter: Optional[str] = None, top_k: int = TOP_K,
             category_filter: Optional[str] = None, min_youtube: int = 2,
             min_news: int = 2, min_web: int = 2) -> list[dict]:
    """Embed question, run cosine similarity search, return top_k chunk dicts.

    Source diversity guarantees:
    - YouTube (min_youtube=2): queries mentioning youtube/video/tutorial bump to 6.
      Fallback score threshold: 0.50.  Skipped when app_filter is set.
    - News (min_news=2): always ensures at least min_news news chunks appear.
      No score threshold - news chunks are short (headline-only until re-scraped)
      and score low vs reviews; any relevant news headline is worth surfacing.
    - Web pages (min_web=2): always ensures at least min_web web_pages chunks.
      No score threshold - official website content should always be represented.
    Both news and web guarantees respect app_filter and category_filter when set.
    """
    q_words = set(question.lower().split())
    if q_words & _YT_KEYWORDS and not app_filter:
        min_youtube = max(min_youtube, 6)

    YT_MIN_SCORE = 0.50

    vec = embed_texts([question])[0]
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # --- Main similarity search ---
            if app_filter:
                cur.execute("""
                    SELECT source, app_name, category, content, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM document_chunks
                    WHERE app_name = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (vec_str, app_filter, vec_str, top_k))
            elif category_filter:
                cur.execute("""
                    SELECT source, app_name, category, content, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM document_chunks
                    WHERE category = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (vec_str, category_filter, vec_str, top_k))
            else:
                cur.execute("""
                    SELECT source, app_name, category, content, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM document_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (vec_str, vec_str, top_k))

            results = [dict(r) for r in cur.fetchall()]

            # --- Guarantee YouTube representation (no app filter only) ---
            if not app_filter and min_youtube > 0:
                yt_count = sum(1 for r in results if r["source"] == "youtube")
                shortfall = min_youtube - yt_count
                if shortfall > 0:
                    existing_contents = {r["content"] for r in results}
                    yt_where = "WHERE source = 'youtube'"
                    yt_params = [vec_str, vec_str, shortfall + 6]
                    if category_filter:
                        yt_where += " AND category = %s"
                        yt_params.insert(1, category_filter)  # slot 1: after score-calc vec, before ORDER BY vec
                    cur.execute(f"""
                        SELECT source, app_name, category, content, metadata,
                               1 - (embedding <=> %s::vector) AS score
                        FROM document_chunks
                        {yt_where}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, yt_params)
                    yt_extras = [
                        dict(r) for r in cur.fetchall()
                        if r["content"] not in existing_contents
                        and float(r["score"]) >= YT_MIN_SCORE
                    ][:shortfall]
                    results = results + yt_extras

            # --- Guarantee news representation ---
            # News chunks are short (RSS headlines only until re-scraped) and score
            # poorly against reviews. Force at least min_news in - any threshold
            # would often exclude them entirely.  Runs even when app_filter is set
            # so app-specific queries still surface relevant press coverage.
            if min_news > 0:
                news_count = sum(1 for r in results if r["source"] == "news")
                shortfall = min_news - news_count
                if shortfall > 0:
                    news_seen = {r["content"] for r in results}
                    news_where = "WHERE source = 'news'"
                    news_params = [vec_str, vec_str, shortfall + 6]
                    if app_filter:
                        news_where += " AND app_name = %s"
                        news_params.insert(1, app_filter)
                    elif category_filter:
                        news_where += " AND category = %s"
                        news_params.insert(1, category_filter)
                    cur.execute(f"""
                        SELECT source, app_name, category, content, metadata,
                               1 - (embedding <=> %s::vector) AS score
                        FROM document_chunks
                        {news_where}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, news_params)
                    news_extras = [
                        dict(r) for r in cur.fetchall()
                        if r["content"] not in news_seen
                    ][:shortfall]
                    results = results + news_extras

            # --- Guarantee web_pages representation ---
            # Official website content (avg 1,700 chars, rich detail) is consistently
            # outranked by the sheer volume of reviews.  Force at least min_web chunks
            # in so every answer includes authoritative product/feature information.
            if min_web > 0:
                web_count = sum(1 for r in results if r["source"] == "web_pages")
                shortfall = min_web - web_count
                if shortfall > 0:
                    web_seen = {r["content"] for r in results}
                    web_where = "WHERE source = 'web_pages'"
                    web_params = [vec_str, vec_str, shortfall + 4]
                    if app_filter:
                        web_where += " AND app_name = %s"
                        web_params.insert(1, app_filter)
                    elif category_filter:
                        web_where += " AND category = %s"
                        web_params.insert(1, category_filter)
                    cur.execute(f"""
                        SELECT source, app_name, category, content, metadata,
                               1 - (embedding <=> %s::vector) AS score
                        FROM document_chunks
                        {web_where}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, web_params)
                    web_extras = [
                        dict(r) for r in cur.fetchall()
                        if r["content"] not in web_seen
                    ][:shortfall]
                    results = results + web_extras

            results.sort(key=lambda r: r["score"], reverse=True)
            return results

    finally:
        conn.close()


def retrieve_by_source(question: str, source: str, top_k: int = TOP_K) -> list[dict]:
    """Retrieve top_k chunks filtered to a specific source type (e.g. 'youtube').
    Used when the user explicitly wants content from one source."""
    vec = embed_texts([question])[0]
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT source, app_name, category, content, metadata,
                       1 - (embedding <=> %s::vector) AS score
                FROM document_chunks
                WHERE source = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (vec_str, source, vec_str, top_k))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def retrieve_per_app(question: str, n_per_app: int = 3,
                     app_list: Optional[list] = None,
                     category_filter: Optional[str] = None) -> list[dict]:
    """Fetch the top n_per_app chunks from EACH app - guarantees all-app coverage.
    Used for comparison queries where global top-K would miss some apps entirely.

    app_list overrides ALL_APPS when provided.
    category_filter restricts which apps are iterated when app_list is None.
    """
    if app_list is None:
        if category_filter == "ev_charging":
            app_list = ALL_EV_APPS
        elif category_filter == "prosumer":
            app_list = ALL_PROSUMER_APPS
        else:
            app_list = ALL_APPS

    vec = embed_texts([question])[0]
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"

    sql = """
        SELECT source, app_name, category, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM document_chunks
        WHERE app_name = %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """

    all_chunks: list[dict] = []
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for app in app_list:
                cur.execute(sql, (vec_str, app, vec_str, n_per_app))
                all_chunks.extend(dict(r) for r in cur.fetchall())
    finally:
        conn.close()

    all_chunks.sort(key=lambda c: c["score"], reverse=True)
    return all_chunks


def generate_answer(question: str, chunks: list[dict]) -> tuple[str, dict]:
    """Send retrieved chunks + question to Claude.

    Returns:
        (answer_text, usage) where usage is a dict with keys:
          input_tokens, output_tokens, total_tokens,
          cache_read_input_tokens, cache_creation_input_tokens
    """
    context = "\n\n---\n\n".join(
        f"[{c['source']} | {c['app_name']} | score: {c['score']:.3f}]\n{c['content']}"
        for c in chunks
    )
    msg = _anthropic.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        }],
    )
    u = msg.usage
    usage = {
        "input_tokens":                  u.input_tokens,
        "output_tokens":                 u.output_tokens,
        "total_tokens":                  u.input_tokens + u.output_tokens,
        "cache_read_input_tokens":       getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens":   getattr(u, "cache_creation_input_tokens", 0) or 0,
    }
    return msg.content[0].text, usage
