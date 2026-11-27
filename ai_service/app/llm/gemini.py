"""Gemini chat client (generateContent REST API)."""

import time

import httpx

from .base import LLMError, LLMResult, Message, google_quota_details, safe_error_message
from .groq import GroqChatModel

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

_FINISH = {"STOP": "stop", "MAX_TOKENS": "length", "SAFETY": "content_filter",
           "RECITATION": "content_filter", "PROHIBITED_CONTENT": "content_filter"}


class GeminiChatModel:
    provider = "gemini"

    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient, *,
                 timeout: float = 20.0, base_url: str = GEMINI_BASE_URL):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.model = model
        self._api_key = api_key
        self._client = client
        self._timeout = timeout
        self._url = f"{base_url}/models/{model}:generateContent"

    async def complete(self, messages: list[Message], *, max_tokens: int, temperature: float = 0.2) -> LLMResult:
        system = "\n\n".join(m.content for m in messages if m.role == "system")
        body = {
            "contents": [
                {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
                for m in messages if m.role != "system"
            ],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        started = time.perf_counter()
        try:
            response = await self._client.post(self._url, json=body, timeout=self._timeout,
                                                headers={"x-goog-api-key": self._api_key})
        except httpx.TimeoutException:
            raise LLMError("Gemini request timed out", provider=self.provider, retryable=True) from None
        except httpx.TransportError as exc:
            raise LLMError(f"Gemini request failed ({type(exc).__name__})", provider=self.provider,
                           retryable=True) from None

        if response.status_code != 200:
            status = response.status_code
            quota_ids, retry_delay = google_quota_details(response) if status == 429 else ([], None)
            raise LLMError(f"Gemini returned HTTP {status}: {safe_error_message(response)}",
                           provider=self.provider, retryable=status == 429 or status >= 500, status=status,
                           retry_after=retry_delay, daily=any("PerDay" in q for q in quota_ids))

        data = response.json()
        candidates = data.get("candidates") or []
        usage = data.get("usageMetadata") or {}
        if not candidates:  # the prompt itself was blocked
            text, finish = "", "content_filter"
        else:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            finish = _FINISH.get(candidates[0].get("finishReason", ""), "unknown")
        return LLMResult(
            text=text.strip(),
            provider=self.provider,
            model=self.model,
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0)),
            finish_reason=finish,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


# ---- Tool calling (My-data mode fallback, Nov 27) ---------------------------------------
#
# Gemini's OpenAI-compatible endpoint takes the same messages, tools and tool results as
# Groq, so a question can switch provider between trips. The owner accepted (Nov 27) that
# their PPA data (question, rows, figures) may go to Gemini when Groq fails; API keys, the
# user's login token and request headers never do (they are not in the messages).

GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

# Schema keywords kept for Gemini; others (anyOf with null, default, format, length limits)
# are removed. The arguments are validated by our own Pydantic models anyway.
_KEEP = {"type", "description", "enum", "items", "properties", "required", "minimum", "maximum"}


def gemini_schema(schema):
    if isinstance(schema, list):
        return [gemini_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    options = schema.get("anyOf")
    if options:
        # Optional[X] in Pydantic is anyOf [X, null]: keep X (and the description).
        real = [o for o in options if o.get("type") != "null"]
        merged = {**(real[0] if real else {}), **{k: v for k, v in schema.items() if k != "anyOf"}}
        return gemini_schema(merged)
    out = {}
    for key, value in schema.items():
        if key not in _KEEP:
            continue
        if key == "properties":
            out[key] = {name: gemini_schema(prop) for name, prop in value.items()}
        elif key == "items":
            out[key] = gemini_schema(value)
        else:
            out[key] = value
    return out


class GeminiToolChatModel(GroqChatModel):
    provider = "gemini"
    label = "Gemini"
    max_tokens_field = "max_tokens"

    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient, *, timeout: float = 20.0,
                 url: str = GEMINI_OPENAI_URL):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        super().__init__(api_key, model, client, timeout=timeout, reasoning_effort=None, url=url)

    def prepare_tools(self, tools: list[dict]) -> list[dict]:
        return [{**t, "function": {**t["function"], "parameters": gemini_schema(t["function"]["parameters"])}}
                for t in tools]
