"""Voltaic API - FastAPI backend that connects the UI to the real hybrid-retrieval
engine and the friend's chosen LLM.

Run (dev):   uvicorn apps.api.main:app --reload --port 8000   (from repo root)
Run (docker): see infra/docker-compose.yml
"""
import sys
from pathlib import Path

# repo root on sys.path so `rag` and `pipeline` import inside the container/dev
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from contextlib import asynccontextmanager        # noqa: E402

from fastapi import FastAPI                       # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from apps.api.core.config import settings         # noqa: E402
from apps.api.core.db_init import ensure_schema   # noqa: E402
from apps.api.routers import auth, chat, stats     # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Self-initialize the schema on a fresh database (cloud deploys).
    try:
        ensure_schema()
    except Exception:
        pass
    yield


app = FastAPI(title="Voltaic API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,        # we use Bearer tokens, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": settings.LLM_PROVIDER,
        "model": settings.default_model,
        "llm_key_set": bool(settings.LLM_API_KEY),
        "db_set": bool(settings.DATABASE_URL),
    }
