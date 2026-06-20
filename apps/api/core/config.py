"""Backend configuration, all driven by environment variables.

The only thing your friend MUST set to make this work is an LLM key:
  LLM_PROVIDER=anthropic   + LLM_API_KEY=sk-ant-...        (Claude)
  LLM_PROVIDER=openai      + LLM_API_KEY=sk-...             (OpenAI)
  LLM_PROVIDER=openai      + LLM_API_KEY=...  + OPENAI_BASE_URL=https://api.deepseek.com   (any OpenAI-compatible)

Embeddings run locally (bge-small) and need NO key.
"""
import os
from pathlib import Path

# apps/api/core/config.py -> repo root is parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_SYSTEM_PROMPT = """\
You are a competitive-intelligence analyst. Answer the user's question using ONLY
the provided context passages, which come from app reviews, news articles, official
web pages, video transcripts, and uploaded documents.

- Be specific and cite app/product names.
- Distinguish user sentiment (reviews) from company claims (web) and reporting (news).
- Surface comparisons and trends when relevant.
- If the context does not contain the answer, say so plainly instead of guessing.
Format with short markdown headings and bold for emphasis where it helps readability."""


class Settings:
    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL", "")

    # LLM provider (the friend's key)
    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    LLM_API_KEY = (
        os.environ.get("LLM_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    LLM_MODEL = os.environ.get("LLM_MODEL", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "")  # OpenAI-compatible endpoints
    MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
    SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

    # Auth
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "720"))
    USERS_FILE = Path(os.environ.get("USERS_FILE", str(REPO_ROOT / "config" / "users.yaml")))

    # CORS (comma-separated origins, or * for any)
    CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]

    @property
    def default_model(self) -> str:
        if self.LLM_MODEL:
            return self.LLM_MODEL
        return "claude-sonnet-4-6" if self.LLM_PROVIDER == "anthropic" else "gpt-4o-mini"


settings = Settings()
