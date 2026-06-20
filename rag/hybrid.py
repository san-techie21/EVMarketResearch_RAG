"""
Hybrid retrieval — the v3 retrieval core.

2026 best practice (verified via current research): two-stage retrieval.
  Stage 1 (recall): run BM25 lexical search AND dense vector search in parallel,
                    fuse the two ranked lists with Reciprocal Rank Fusion (RRF).
  Stage 2 (precision): re-score the fused candidate pool with a cross-encoder
                    reranker and keep the best top_k for the LLM.

Why this replaces the v2 approach: v2 used pure cosine top-K, which drowned out
minority sources (news/web/youtube), and propped them up with forced
"guarantee" injectors that had no relevance gate. Hybrid + rerank fixes this
properly — lexical search catches exact names ("Supercharger", "Powerwall 3",
error codes) that embeddings miss, and the reranker lets good minority-source
chunks rank up on merit, so the injector hacks can be deleted.

This module is self-contained and does NOT modify rag/retriever.py, so the
existing Streamlit app keeps working during the migration. The new FastAPI
backend imports `hybrid_retrieve` from here.

Env:
  RERANKER_MODEL     default "cross-encoder/ms-marco-MiniLM-L-6-v2" (small/fast,
                     CPU-friendly). Quality upgrade: "BAAI/bge-reranker-v2-m3".
  HYBRID_CANDIDATES  default 40  (pool size per retriever before fusion)
  RAG_TOP_K          default 10  (chunks returned after rerank)
  USE_RERANKER       default "1" ("0" disables the cross-encoder; RRF order used)
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

import psycopg2
import psycopg2.extras

from rag.retriever import _get_conn, embed_texts  # reuse DB + embedder

log = logging.getLogger(__name__)

RERANKER_MODEL    = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
HYBRID_CANDIDATES = int(os.environ.get("HYBRID_CANDIDATES", 40))
RAG_TOP_K         = int(os.environ.get("RAG_TOP_K", 10))
USE_RERANKER      = os.environ.get("USE_RERANKER", "1") != "0"

# Cached once: does the table have the indexed content_tsv column (v3 migration)?
_HAS_TSV: Optional[bool] = None


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion  (pure function — unit-testable without a DB)
# ---------------------------------------------------------------------------
def reciprocal_rank_fusion(result_lists: list[list[dict]], k: int = 60) -> list[dict]:
    """Fuse multiple ranked lists into one. Each list is ordered best-first.

    RRF score for a doc = sum over lists of 1 / (k + rank). Rank-based, so it
    sidesteps the fact that cosine scores and BM25 scores live on different
    scales. Documents are keyed by their `content` string.
    """
    scores: dict[str, float] = {}
    store:  dict[str, dict]  = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            key = item["content"]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            if key not in store:
                store[key] = item
    fused = list(store.values())
    for it in fused:
        it["rrf_score"] = scores[it["content"]]
    fused.sort(key=lambda it: it["rrf_score"], reverse=True)
    return fused


# ---------------------------------------------------------------------------
# Cross-encoder reranker  (lazy-loaded, optional)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _get_reranker():
    from sentence_transformers import CrossEncoder
    log.info("Loading reranker %s ...", RERANKER_MODEL)
    return CrossEncoder(RERANKER_MODEL)


def rerank(question: str, chunks: list[dict], top_k: int) -> list[dict]:
    """Re-score candidates with the cross-encoder; fall back to RRF order."""
    if not chunks:
        return []
    if not USE_RERANKER:
        return sorted(chunks, key=lambda c: c.get("rrf_score", c.get("score", 0)),
                      reverse=True)[:top_k]
    try:
        ce = _get_reranker()
        pairs = [[question, c["content"]] for c in chunks]
        scores = ce.predict(pairs, show_progress_bar=False)
        for c, s in zip(chunks, scores):
            c["rerank_score"] = float(s)
        chunks.sort(key=lambda c: c["rerank_score"], reverse=True)
    except Exception as exc:
        log.warning("Reranker unavailable (%s); using RRF order.", exc)
        chunks.sort(key=lambda c: c.get("rrf_score", c.get("score", 0)), reverse=True)
    return chunks[:top_k]


# ---------------------------------------------------------------------------
# Stage 1 retrievers
# ---------------------------------------------------------------------------
def _where_clause(app_filter, category_filter) -> tuple[str, list]:
    clauses, params = [], []
    if app_filter:
        clauses.append("app_name = %s")
        params.append(app_filter)
    elif category_filter:
        clauses.append("category = %s")
        params.append(category_filter)
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _vector_search(cur, vec_str, where, where_params, limit) -> list[dict]:
    cur.execute(f"""
        SELECT source, app_name, category, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM document_chunks
        WHERE TRUE {where}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, [vec_str, *where_params, vec_str, limit])
    return [dict(r) for r in cur.fetchall()]


def _tsv_expr() -> str:
    """Return the tsvector SQL expression, using the indexed column if present."""
    global _HAS_TSV
    if _HAS_TSV is None:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='document_chunks' AND column_name='content_tsv'
                """)
                _HAS_TSV = cur.fetchone() is not None
        except Exception:
            _HAS_TSV = False
        finally:
            conn.close()
        log.info("Hybrid keyword search using %s",
                 "indexed content_tsv column" if _HAS_TSV else "on-the-fly to_tsvector")
    return "content_tsv" if _HAS_TSV else "to_tsvector('english', content)"


def _keyword_search(cur, query, where, where_params, limit) -> list[dict]:
    tsv = _tsv_expr()
    # websearch_to_tsquery handles natural phrasing/quotes/operators gracefully.
    cur.execute(f"""
        SELECT source, app_name, category, content, metadata,
               ts_rank_cd({tsv}, websearch_to_tsquery('english', %s)) AS score
        FROM document_chunks
        WHERE {tsv} @@ websearch_to_tsquery('english', %s) {where}
        ORDER BY score DESC
        LIMIT %s
    """, [query, query, *where_params, limit])
    return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def hybrid_retrieve(question: str,
                    app_filter: Optional[str] = None,
                    category_filter: Optional[str] = None,
                    top_k: int = RAG_TOP_K,
                    candidates: int = HYBRID_CANDIDATES,
                    use_reranker: Optional[bool] = None) -> list[dict]:
    """Hybrid (BM25 + vector) → RRF → rerank. Returns top_k chunk dicts.

    Each returned chunk has: source, app_name, category, content, metadata,
    score (vector cosine if available), rrf_score, and rerank_score (if reranked).
    """
    vec = embed_texts([question])[0]
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
    where, where_params = _where_clause(app_filter, category_filter)

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            vec_hits = _vector_search(cur, vec_str, where, where_params, candidates)
            try:
                kw_hits = _keyword_search(cur, question, where, where_params, candidates)
            except Exception as exc:
                # Never let a BM25 hiccup break retrieval — degrade to vector-only.
                log.warning("Keyword search failed (%s); vector-only.", exc)
                conn.rollback()
                kw_hits = []
    finally:
        conn.close()

    fused = reciprocal_rank_fusion([vec_hits, kw_hits])

    do_rerank = USE_RERANKER if use_reranker is None else use_reranker
    if do_rerank:
        return rerank(question, fused[: max(candidates, top_k)], top_k)
    return fused[:top_k]
