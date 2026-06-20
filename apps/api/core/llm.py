"""Provider-agnostic LLM call. Supports Anthropic and OpenAI (and any
OpenAI-compatible endpoint via OPENAI_BASE_URL, e.g. DeepSeek / Groq / Together).

The SDK is imported lazily so the server starts even if one provider's package
isn't installed."""
from __future__ import annotations

from apps.api.core.config import settings


class LLMError(RuntimeError):
    pass


def generate(question: str, context: str) -> tuple[str, dict]:
    """Return (answer_text, usage_dict)."""
    if not settings.LLM_API_KEY:
        raise LLMError(
            "No LLM API key configured. Set LLM_API_KEY (and LLM_PROVIDER) in the environment."
        )

    user = f"Context:\n{context}\n\nQuestion: {question}"
    model = settings.default_model

    if settings.LLM_PROVIDER == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)
        msg = client.messages.create(
            model=model,
            max_tokens=settings.MAX_TOKENS,
            system=settings.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        u = msg.usage
        usage = {
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "total_tokens": u.input_tokens + u.output_tokens,
        }
        return msg.content[0].text, usage

    # openai or OpenAI-compatible
    from openai import OpenAI

    kwargs: dict = {"api_key": settings.LLM_API_KEY}
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=settings.MAX_TOKENS,
        messages=[
            {"role": "system", "content": settings.SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    )
    usage = {}
    if resp.usage:
        usage = {
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        }
    return resp.choices[0].message.content or "", usage
