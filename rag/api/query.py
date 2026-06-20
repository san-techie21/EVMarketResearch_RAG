"""
RAG query API - FastAPI endpoint for the EV charging knowledge base.

Run with:
    uvicorn rag.api.query:app --reload --port 8000
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from rag.retriever import TOP_K, generate_answer, retrieve

app = FastAPI(title="EV Research RAG API", version="1.0")


class QueryRequest(BaseModel):
    question: str
    app_filter: Optional[str] = None
    top_k: int = TOP_K


class Source(BaseModel):
    app_name: str
    source: str
    content: str
    score: float
    metadata: dict


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    chunks = retrieve(req.question, req.app_filter, req.top_k)
    if not chunks:
        return QueryResponse(answer="No relevant documents found.", sources=[])

    answer = generate_answer(req.question, chunks)
    sources = [
        Source(
            app_name=c["app_name"],
            source=c["source"],
            content=c["content"][:400] + "…" if len(c["content"]) > 400 else c["content"],
            score=float(c["score"]),
            metadata=c["metadata"] if isinstance(c["metadata"], dict) else {},
        )
        for c in chunks
    ]
    return QueryResponse(answer=answer, sources=sources)
