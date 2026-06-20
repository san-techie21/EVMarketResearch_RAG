"""
ragas_eval.py - Async batch RAGAs evaluator.

Runs in a background thread, waking every EVAL_INTERVAL_SECS (default: 30 min).
Each wake: picks up to BATCH_SIZE unevaluated queries, scores them with RAGAs
using Claude Haiku as the LLM judge, and stores results in ragas_scores.

Metrics evaluated (reference-free - no ground truth needed):
  - faithfulness:       answer grounded in the retrieved context?
  - answer_relevancy:   answer actually addresses the question?
  - context_precision:  retrieved chunks relevant to the question?

Why Haiku as judge?
  Claude Haiku is ~20x cheaper than Sonnet and accurate enough for LLM-as-judge
  scoring. At ~5 LLM calls per query, 10 queries/batch ≈ 50 Haiku calls ≈ $0.01.
"""
import os
import sys
import json
import logging
import threading
import time
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parents[2]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[2] / "config" / ".env", override=True)

from rag.chat_ui.obs_db import (
    get_unevaluated_queries,
    save_ragas_score,
)

log = logging.getLogger("ragas_eval")

EVAL_INTERVAL_SECS = 1800   # 30 minutes between evaluation sweeps
BATCH_SIZE         = 10     # max queries to evaluate per sweep
EVAL_MODEL         = "claude-haiku-4-5"   # cheap, fast judge

_EVAL_STARTED = False
_EVAL_LOCK    = threading.Lock()


# -- Core evaluation logic ------------------------------------------------------

def _build_llm():
    """Build a LangChain-wrapped Claude Haiku for use as RAGAs judge."""
    from langchain_anthropic import ChatAnthropic
    from ragas.llms import LangchainLLMWrapper
    return LangchainLLMWrapper(
        ChatAnthropic(
            model=EVAL_MODEL,
            api_key=os.environ["ANTHROPIC_API_KEY"],
            temperature=0,
            max_tokens=1024,
        )
    )


def _build_embeddings():
    """Build a LangChain-wrapped embedder for RAGAs Answer Relevancy metric."""
    from langchain_anthropic import ChatAnthropic
    from ragas.embeddings import LangchainEmbeddingsWrapper
    # Use a simple sentence-transformer via HuggingFace for embeddings
    # (avoids an extra API key; we already have the model locally)
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    )


def evaluate_one(query_id: int, question: str, answer: str, context_chunks: list) -> dict:
    """
    Run RAGAs on a single query. Returns a dict with metric scores.
    Raises on failure - caller handles the exception.
    """
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision

    # RAGAs expects contexts as a list of strings
    contexts = [c["content"] for c in context_chunks if c.get("content")]
    if not contexts:
        raise ValueError("No context chunks to evaluate")

    dataset = Dataset.from_dict({
        "question":  [question],
        "answer":    [answer],
        "contexts":  [contexts],
        # context_precision requires ground_truth - we omit it, metric will be skipped
    })

    llm = _build_llm()

    # Build metrics - context_precision needs ground_truth, use without it
    metrics = [
        faithfulness,
        answer_relevancy,
    ]

    # Try to also run context_precision (needs ground_truth; skip if it fails)
    try:
        cp_metric = context_precision
        test_metrics = metrics + [cp_metric]
        result = evaluate(
            dataset=dataset,
            metrics=test_metrics,
            llm=llm,
            raise_exceptions=False,
        )
    except Exception:
        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=llm,
            raise_exceptions=False,
        )

    df = result.to_pandas()
    row = df.iloc[0]
    return {
        "faithfulness":      float(row.get("faithfulness",      float("nan"))) if "faithfulness"      in row else None,
        "answer_relevancy":  float(row.get("answer_relevancy",  float("nan"))) if "answer_relevancy"  in row else None,
        "context_precision": float(row.get("context_precision", float("nan"))) if "context_precision" in row else None,
    }


def _safe_float(v) -> float | None:
    """Return None for NaN/None, otherwise float."""
    import math
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def run_eval_batch():
    """Evaluate a batch of unevaluated queries. Called by scheduler and manual trigger."""
    pending = get_unevaluated_queries(limit=BATCH_SIZE)
    if not pending:
        log.debug("RAGAs: no pending queries to evaluate")
        return 0

    log.info("RAGAs: evaluating %d queries", len(pending))
    evaluated = 0

    for row in pending:
        qid      = row["id"]
        question = row["question"]
        answer   = row["answer_text"]
        ctx_raw  = row["context_chunks"]

        try:
            if isinstance(ctx_raw, str):
                ctx_raw = json.loads(ctx_raw)
            scores = evaluate_one(qid, question, answer, ctx_raw or [])
            save_ragas_score(
                query_log_id      = qid,
                faithfulness      = _safe_float(scores.get("faithfulness")),
                answer_relevancy  = _safe_float(scores.get("answer_relevancy")),
                context_precision = _safe_float(scores.get("context_precision")),
                eval_model        = EVAL_MODEL,
            )
            log.info(
                "RAGAs [qid=%d] faith=%.3f relevancy=%.3f",
                qid,
                scores.get("faithfulness") or 0,
                scores.get("answer_relevancy") or 0,
            )
            evaluated += 1
        except Exception as exc:
            log.warning("RAGAs [qid=%d] evaluation failed: %s", qid, exc)
            save_ragas_score(
                query_log_id      = qid,
                faithfulness      = None,
                answer_relevancy  = None,
                context_precision = None,
                eval_model        = EVAL_MODEL,
                error             = str(exc)[:300],
            )

    return evaluated


# -- Background scheduler -------------------------------------------------------

def _eval_loop():
    """Infinite loop: sleep → evaluate batch → repeat."""
    # Initial delay so app starts up cleanly before first eval run
    time.sleep(120)
    while True:
        try:
            n = run_eval_batch()
            if n:
                log.info("RAGAs: completed batch of %d evaluations", n)
        except Exception as exc:
            log.warning("RAGAs scheduler error: %s", exc)
        time.sleep(EVAL_INTERVAL_SECS)


def start_ragas_scheduler():
    """Start the background evaluator thread (once per process lifetime)."""
    global _EVAL_STARTED
    with _EVAL_LOCK:
        if not _EVAL_STARTED:
            _EVAL_STARTED = True
            t = threading.Thread(target=_eval_loop, daemon=True, name="ragas-evaluator")
            t.start()
            log.info("RAGAs background evaluator started (interval=%ds, batch=%d)",
                     EVAL_INTERVAL_SECS, BATCH_SIZE)
