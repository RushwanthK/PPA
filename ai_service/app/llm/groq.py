"""Groq chat client (OpenAI-compatible Chat Completions API).

GeminiToolChatModel (gemini.py) reuses this client through Gemini's OpenAI-compatible
endpoint, so My-data mode can fall back to Gemini with the same messages and tools."""

import logging
import time
from dataclasses import dataclass, field

import httpx

from .base import LLMError, LLMResult, Message, parse_seconds, safe_error_message

log = logging.getLogger("ppa_ai.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON text written by the model: validate before use


@dataclass(frozen=True)
class ToolChatResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: str = "groq"
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = "unknown"
    latency_ms: int = 0

    def assistant_message(self) -> dict:
        """The model's turn, to send back with the tool results in the next round."""
        message: dict = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            message["tool_calls"] = [{"id": c.id, "type": "function",
                                      "function": {"name": c.name, "arguments": c.arguments}}
                                     for c in self.tool_calls]
        return message


class GroqChatModel:
    provider = "groq"
    label = "Groq"                          # used in error messages
    max_tokens_field = "max_completion_tokens"

    def __init__(self, api_key: str, model: str, client: httpx.AsyncClient, *,
                 timeout: float = 20.0, reasoning_effort: str | None = "low", url: str = GROQ_URL):
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self.model = model
        self._api_key = api_key
        self._client = client
        self._timeout = timeout
        # gpt-oss models "think" before answering; those tokens count against limits.
        # Low effort is enough for answering from provided sources.
        self._reasoning_effort = reasoning_effort
        self._url = url

    async def complete(self, messages: list[Message], *, max_tokens: int, temperature: float = 0.2) -> LLMResult:
        result = await self.chat([{"role": m.role, "content": m.content} for m in messages],
                                 max_tokens=max_tokens, temperature=temperature)
        return LLMResult(result.text, result.provider, result.model, result.input_tokens, result.output_tokens,
                         result.finish_reason, result.latency_ms)

    async def chat(self, messages: list[dict], *, max_tokens: int, temperature: float = 0.2,
                   tools: list[dict] | None = None, tool_choice: str | None = None) -> ToolChatResult:
        """Chat Completions with optional tool calling. `messages` are OpenAI-format dicts,
        so assistant tool calls and tool results can be sent back in the next round."""
        body = {
            "model": self.model,
            "messages": messages,
            self.max_tokens_field: max_tokens,
            "temperature": temperature,
        }
        if tools:
            body["tools"] = self.prepare_tools(tools)
            body["tool_choice"] = tool_choice or "auto"
        if self._reasoning_effort:
            body["reasoning_effort"] = self._reasoning_effort
            if self.provider == "groq":
                body["include_reasoning"] = False  # don't send the hidden reasoning back to us
        started = time.perf_counter()
        try:
            response = await self._client.post(
                self._url, json=body, timeout=self._timeout,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except httpx.TimeoutException:
            raise LLMError(f"{self.label} request timed out", provider=self.provider, retryable=True) from None
        except httpx.TransportError as exc:
            raise LLMError(f"{self.label} request failed ({type(exc).__name__})", provider=self.provider,
                           retryable=True) from None

        if response.status_code != 200:
            status = response.status_code
            detail = safe_error_message(response)
            # On 429 Groq sends Retry-After, and the message names the limit,
            # e.g. "... on tokens per day (TPD): Limit 200000 ...".
            raise LLMError(f"{self.label} returned HTTP {status}: {detail}",
                           provider=self.provider, retryable=status == 429 or status >= 500, status=status,
                           retry_after=parse_seconds(response.headers.get("retry-after")) if status == 429 else None,
                           daily=status == 429 and "per day" in detail.lower())
        if self.provider == "groq":
            watch_quota(response.headers)

        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        # Every tool call needs an id to link its result; make one if the provider sent none.
        calls = [ToolCall(str(c.get("id") or f"call_{i}"), str(c.get("function", {}).get("name", "")),
                          str(c.get("function", {}).get("arguments") or "{}"))
                 for i, c in enumerate(message.get("tool_calls") or [], 1)]
        return ToolChatResult(
            text=(message.get("content") or "").strip(),
            tool_calls=calls,
            provider=self.provider,
            model=self.model,
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            finish_reason=choice.get("finish_reason") or "unknown",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


    def prepare_tools(self, tools: list[dict]) -> list[dict]:
        return tools


QUOTA_WARN_FRACTION = 0.1


def watch_quota(headers) -> None:
    """Monitoring for free: every Groq reply says how much of the limit is left.
    Warn when under 10%, so the logs show trouble before users see 503s.
    Requests are the per-day limit (RPD); tokens are the per-minute limit (TPM)."""
    for kind in ("requests", "tokens"):
        limit = parse_seconds(headers.get(f"x-ratelimit-limit-{kind}"))
        remaining = parse_seconds(headers.get(f"x-ratelimit-remaining-{kind}"))
        if limit and remaining is not None and remaining < limit * QUOTA_WARN_FRACTION:
            log.warning("Groq %s quota is running low", kind,
                        extra={"provider": "groq", f"remaining_{kind}": int(remaining), f"limit_{kind}": int(limit)})
