import json

import httpx
import pytest

from app.llm.base import LLMError, LLMResult, Message
from app.llm.gemini import GeminiChatModel
from app.llm.groq import GroqChatModel
from app.llm.router import FallbackChatModel

KEY = "secret-key-never-in-errors"
MESSAGES = [Message("system", "be brief"), Message("user", "hi"), Message("assistant", "hello"),
            Message("user", "what is a SIP?")]


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ---- Groq ------------------------------------------------------------------------

async def test_groq_request_and_response():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": " A SIP is... [S1] "},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 45},
        })

    result = await GroqChatModel(KEY, "openai/gpt-oss-120b", client(handler)).complete(MESSAGES, max_tokens=300)
    assert result.text == "A SIP is... [S1]"
    assert (result.provider, result.input_tokens, result.output_tokens, result.finish_reason) == \
        ("groq", 120, 45, "stop")
    request = seen[0]
    assert request.headers["authorization"] == f"Bearer {KEY}"
    assert KEY not in str(request.url)
    body = json.loads(request.content)
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["max_completion_tokens"] == 300
    assert body["reasoning_effort"] == "low" and body["include_reasoning"] is False
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user"]


@pytest.mark.parametrize("status,retryable", [(429, True), (500, True), (503, True), (400, False), (401, False)])
async def test_groq_errors_are_classified(status, retryable):
    model = GroqChatModel(KEY, "m", client(lambda r: httpx.Response(status, json={"error": {"message": "x"}})))
    with pytest.raises(LLMError) as info:
        await model.complete(MESSAGES, max_tokens=10)
    assert info.value.retryable is retryable
    assert info.value.status == status
    assert KEY not in str(info.value)


async def test_groq_timeout_is_retryable():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError) as info:
        await GroqChatModel(KEY, "m", client(handler)).complete(MESSAGES, max_tokens=10)
    assert info.value.retryable and "timed out" in str(info.value)


# ---- Gemini ----------------------------------------------------------------------

async def test_gemini_request_mapping_and_thinking_tokens():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": "hidden", "thought": True}, {"text": "Answer [S1]"}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 20, "thoughtsTokenCount": 30},
        })

    result = await GeminiChatModel(KEY, "gemini-3.5-flash-lite", client(handler)).complete(MESSAGES, max_tokens=200)
    assert result.text == "Answer [S1]"           # thought parts are not shown
    assert result.output_tokens == 50              # thinking tokens are counted
    request = seen[0]
    assert request.url.path.endswith("/models/gemini-3.5-flash-lite:generateContent")
    assert request.headers["x-goog-api-key"] == KEY and KEY not in str(request.url)
    body = json.loads(request.content)
    assert body["systemInstruction"]["parts"][0]["text"] == "be brief"
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]
    assert body["generationConfig"]["maxOutputTokens"] == 200


async def test_gemini_safety_block_and_empty_candidates():
    blocked = await GeminiChatModel(KEY, "m", client(lambda r: httpx.Response(200, json={
        "candidates": [{"content": {"parts": []}, "finishReason": "SAFETY"}]}))).complete(MESSAGES, max_tokens=10)
    assert blocked.finish_reason == "content_filter" and blocked.text == ""
    empty = await GeminiChatModel(KEY, "m", client(lambda r: httpx.Response(200, json={
        "promptFeedback": {"blockReason": "SAFETY"}}))).complete(MESSAGES, max_tokens=10)
    assert empty.finish_reason == "content_filter"


async def test_gemini_rate_limit_is_retryable():
    model = GeminiChatModel(KEY, "m", client(lambda r: httpx.Response(429, json={"error": {"message": "quota"}})))
    with pytest.raises(LLMError) as info:
        await model.complete(MESSAGES, max_tokens=10)
    assert info.value.retryable and KEY not in str(info.value)


# ---- Fallback router ----------------------------------------------------------------

class StubModel:
    def __init__(self, provider, outcome):
        self.provider, self.model, self.outcome, self.calls = provider, f"{provider}-model", outcome, 0

    async def complete(self, messages, *, max_tokens, temperature=0.2):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return LLMResult(self.outcome, self.provider, self.model, 1, 1, "stop", 5)


async def test_fallback_used_when_primary_is_rate_limited():
    groq = StubModel("groq", LLMError("429", provider="groq", retryable=True, status=429))
    gemini = StubModel("gemini", "from gemini")
    result = await FallbackChatModel([groq, gemini]).complete(MESSAGES, max_tokens=10)
    assert result.provider == "gemini" and result.text == "from gemini"
    assert groq.calls == gemini.calls == 1


async def test_primary_answer_does_not_touch_fallback():
    groq, gemini = StubModel("groq", "fast"), StubModel("gemini", "slow")
    assert (await FallbackChatModel([groq, gemini]).complete(MESSAGES, max_tokens=10)).provider == "groq"
    assert gemini.calls == 0


async def test_non_retryable_error_is_not_hidden_by_fallback():
    groq = StubModel("groq", LLMError("400 bad request", provider="groq", retryable=False, status=400))
    gemini = StubModel("gemini", "x")
    with pytest.raises(LLMError, match="400"):
        await FallbackChatModel([groq, gemini]).complete(MESSAGES, max_tokens=10)
    assert gemini.calls == 0


async def test_all_providers_down_raises_last_error():
    models = [StubModel("groq", LLMError("down", provider="groq", retryable=True)),
              StubModel("gemini", LLMError("also down", provider="gemini", retryable=True))]
    with pytest.raises(LLMError, match="also down"):
        await FallbackChatModel(models).complete(MESSAGES, max_tokens=10)


# ---- How long to wait (used for the 503 message) ------------------------------------------

async def test_groq_429_reports_retry_after_and_daily_limit():
    def handler(request):
        return httpx.Response(429, headers={"retry-after": "38"}, json={"error": {
            "message": "Rate limit reached for model on tokens per day (TPD): Limit 200000"}})
    with pytest.raises(LLMError) as info:
        await GroqChatModel(KEY, "m", client(handler)).complete(MESSAGES, max_tokens=10)
    assert info.value.retry_after == 38 and info.value.daily


async def test_groq_per_minute_429_is_not_daily():
    def handler(request):
        return httpx.Response(429, headers={"retry-after": "2"}, json={"error": {
            "message": "Rate limit reached on tokens per minute (TPM)"}})
    with pytest.raises(LLMError) as info:
        await GroqChatModel(KEY, "m", client(handler)).complete(MESSAGES, max_tokens=10)
    assert info.value.retry_after == 2 and not info.value.daily


async def test_gemini_429_reads_quota_details():
    body = {"error": {"message": "quota", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
         "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "21s"}]}}
    with pytest.raises(LLMError) as info:
        await GeminiChatModel(KEY, "m", client(lambda r: httpx.Response(429, json=body))).complete(
            MESSAGES, max_tokens=10)
    assert info.value.daily and info.value.retry_after == 21


async def test_all_down_reports_the_shortest_known_wait():
    models = [StubModel("groq", LLMError("busy", provider="groq", retryable=True, retry_after=40)),
              StubModel("gemini", LLMError("busy", provider="gemini", retryable=True, retry_after=9))]
    with pytest.raises(LLMError) as info:
        await FallbackChatModel(models).complete(MESSAGES, max_tokens=10)
    assert info.value.retry_after == 9 and not info.value.daily


async def test_all_down_with_an_unknown_wait_reports_none():
    models = [StubModel("groq", LLMError("500", provider="groq", retryable=True, status=500)),
              StubModel("gemini", LLMError("busy", provider="gemini", retryable=True, retry_after=9))]
    with pytest.raises(LLMError) as info:
        await FallbackChatModel(models).complete(MESSAGES, max_tokens=10)
    assert info.value.retry_after is None


# ---- Gemini tool calling (My-data fallback, Nov 27) -------------------------------------

async def test_gemini_tool_client_uses_the_openai_compatible_endpoint():
    from app.assistant.tools import TOOL_SCHEMAS
    from app.llm.gemini import GEMINI_OPENAI_URL, GeminiToolChatModel
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"type": "function", "function": {"name": "query_transactions", "arguments": '{"terms": ["goa"]}'}}]},
                "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 900, "completion_tokens": 30},
        })

    model = GeminiToolChatModel(KEY, "gemini-3.5-flash-lite", client(handler))
    result = await model.chat([{"role": "user", "content": "goa?"}], max_tokens=200,
                              tools=TOOL_SCHEMAS, tool_choice="required")
    assert str(seen[0].url) == GEMINI_OPENAI_URL and seen[0].headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(seen[0].content)
    assert body["max_tokens"] == 200 and "max_completion_tokens" not in body
    assert "reasoning_effort" not in body and "include_reasoning" not in body
    assert body["tool_choice"] == "required"
    # Optional fields are simplified for Gemini: no anyOf/null, defaults or formats.
    sent = json.dumps(body["tools"])
    assert "anyOf" not in sent and '"default"' not in sent and '"format"' not in sent
    query = next(t for t in body["tools"] if t["function"]["name"] == "query_transactions")
    assert query["function"]["parameters"]["properties"]["start_date"]["type"] == "string"
    # Gemini may send tool calls without ids; every call still gets one.
    assert result.provider == "gemini" and result.tool_calls[0].id == "call_1"
    assert (result.input_tokens, result.output_tokens) == (900, 30)


async def test_gemini_tool_client_errors_name_gemini_and_hide_the_key():
    from app.llm.gemini import GeminiToolChatModel

    def handler(request):
        return httpx.Response(429, json={"error": {"message": "quota"}}, headers={"retry-after": "20"})

    with pytest.raises(LLMError) as exc:
        await GeminiToolChatModel(KEY, "gemini-3.5-flash-lite", client(handler)).chat(
            [{"role": "user", "content": "hi"}], max_tokens=50)
    assert str(exc.value).startswith("Gemini returned HTTP 429") and KEY not in str(exc.value)
    assert exc.value.provider == "gemini" and exc.value.retryable
