"""The real chat endpoint: hybrid retrieval -> the configured LLM -> cited answer."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apps.api.core import llm
from apps.api.routers.auth import get_current_user

router = APIRouter(prefix="/api", tags=["chat"])

CATEGORY_MAP = {"EV Charging": "ev_charging", "Prosumer": "prosumer"}


class ChatReq(BaseModel):
    question: str
    category: Optional[str] = None
    app: Optional[str] = None


@router.post("/chat")
def chat(req: ChatReq, user: dict = Depends(get_current_user)):
    # imported here so the server boots without the heavy torch stack until first use
    from rag.hybrid import hybrid_retrieve

    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    category = CATEGORY_MAP.get(req.category or "")
    try:
        chunks = hybrid_retrieve(q, app_filter=req.app or None, category_filter=category)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}")

    if not chunks:
        return {
            "answer": "I couldn't find anything relevant in the knowledge base for that. "
            "Try rephrasing, or add more documents and re-run ingestion.",
            "sources": [],
        }

    context = "\n\n---\n\n".join(
        f"[{c['source']} | {c['app_name']}]\n{c['content']}" for c in chunks
    )
    try:
        answer, usage = llm.generate(q, context)
    except llm.LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}")

    sources = [
        {
            "app": c["app_name"],
            "source": c["source"],
            "score": round(float(c.get("score") or c.get("rrf_score") or 0.0), 3),
            "snippet": c["content"][:400] + ("…" if len(c["content"]) > 400 else ""),
        }
        for c in chunks
    ]
    return {"answer": answer, "sources": sources, "usage": usage}
