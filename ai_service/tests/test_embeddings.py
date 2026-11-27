import asyncio
import json

import httpx
import pytest

from app.rag import embeddings as emb
from app.rag.embeddings import EmbeddingError, FakeEmbedder, GeminiEmbedder, vector_literal

KEY = "test-key-should-never-leak"


def make(handler, *, dims=4, batch_size=50, max_retries=3):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return GeminiEmbedder(KEY, "gemini-embedding-001", dims, client=client,
                          batch_size=batch_size, max_retries=max_retries)


def ok_response(request: httpx.Request, dims=4):
    n = len(json.loads(request.content)["requests"])
    return httpx.Response(200, json={"embeddings": [{"values": [0.1] * dims} for _ in range(n)]})


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def _sleep(_):
        pass
    monkeypatch.setattr(emb.asyncio, "sleep", _sleep)


async def test_request_shape_and_key_in_header_not_url():
    seen = []

    def handler(request):
        seen.append(request)
        return ok_response(request)

    vectors = await make(handler).embed_documents(["hello", "world"])
    assert vectors == [[0.1] * 4, [0.1] * 4]
    request = seen[0]
    assert request.url.path.endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert KEY not in str(request.url)
    assert request.headers["x-goog-api-key"] == KEY
    body = json.loads(request.content)
    assert body["requests"][0] == {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": "hello"}]},
        "taskType": "RETRIEVAL_DOCUMENT",
        "outputDimensionality": 4,
    }


async def test_queries_use_query_task_type():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return ok_response(request)

    await make(handler).embed_queries(["q"])
    assert seen[0]["requests"][0]["taskType"] == "RETRIEVAL_QUERY"


async def test_large_inputs_are_batched_and_usage_counted():
    sizes = []

    def handler(request):
        sizes.append(len(json.loads(request.content)["requests"]))
        return ok_response(request)

    embedder = make(handler, batch_size=3)
    vectors = await embedder.embed_documents(["abcd"] * 7)
    assert len(vectors) == 7
    assert sizes == [3, 3, 1]
    assert embedder.usage.requests == 3
    assert embedder.usage.texts == 7
    assert embedder.usage.estimated_tokens == 7


async def test_rate_limit_is_retried_then_succeeds():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(429, headers={"retry-after": "1"}, json={"error": {"message": "slow down"}})
        return ok_response(request)

    embedder = make(handler)
    assert len(await embedder.embed_documents(["x"])) == 1
    assert calls == 3
    assert embedder.usage.requests == 3


async def test_gives_up_after_max_retries():
    def handler(request):
        return httpx.Response(503, json={"error": {"message": "unavailable"}})

    with pytest.raises(EmbeddingError, match="503"):
        await make(handler, max_retries=2).embed_documents(["x"])


async def test_client_error_is_not_retried_and_does_not_leak_key():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": {"message": "API key not valid"}})

    with pytest.raises(EmbeddingError) as info:
        await make(handler).embed_documents(["x"])
    assert calls == 1
    assert KEY not in str(info.value)


async def test_network_errors_are_retried_without_leaking_key():
    def handler(request):
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(EmbeddingError) as info:
        await make(handler, max_retries=1).embed_documents(["x"])
    assert "ConnectError" in str(info.value)
    assert KEY not in str(info.value)


async def test_wrong_dimension_is_rejected():
    def handler(request):
        return ok_response(request, dims=3)

    with pytest.raises(EmbeddingError, match="Expected 4 dimensions"):
        await make(handler, dims=4).embed_documents(["x"])


def test_missing_key_is_rejected():
    with pytest.raises(ValueError):
        GeminiEmbedder("", "m", 4)


def test_vector_literal_format():
    assert vector_literal([0.5, -1.0, 0.123456789]) == "[0.5,-1,0.1234568]"


async def test_fake_embedder_is_deterministic_and_normalised():
    fake = FakeEmbedder(dimensions=64)
    a, b, c = await fake.embed_documents(["credit card payment", "credit card payment", "emergency fund"])
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-9
    assert a != c


# ---- Rate limiting and quota handling -------------------------------------------

class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


async def test_limiter_waits_when_the_minute_budget_is_used(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(emb.asyncio, "sleep", clock.sleep)
    limiter = emb.SlidingWindowLimiter(10, 60.0, clock=clock)
    assert await limiter.acquire(6) == 0
    assert await limiter.acquire(4) == 0      # exactly at the limit
    waited = await limiter.acquire(1)         # must wait for the first batch to age out
    assert 60 <= waited < 61
    assert clock.now >= 60


def test_limiter_rejects_a_batch_bigger_than_the_limit():
    limiter = emb.SlidingWindowLimiter(5, 60.0)
    with pytest.raises(ValueError):
        asyncio.run(limiter.acquire(6))


async def test_embedder_throttles_instead_of_hitting_429(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(emb.asyncio, "sleep", clock.sleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(ok_response))
    embedder = GeminiEmbedder(KEY, "m", 4, client=client, batch_size=50,
                              texts_per_minute=5, clock=clock)
    await embedder.embed_documents(["t"] * 12)  # batches of 5, 5, 2
    assert embedder.usage.requests == 3
    assert embedder.usage.throttled_seconds >= 120  # two full-minute waits


def quota_error(quota_id, retry_delay="7s"):
    return httpx.Response(429, json={"error": {
        "message": "You exceeded your current quota",
        "details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
             "violations": [{"quotaId": quota_id}]},
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay},
        ],
    }})


async def test_retry_delay_from_google_error_is_honoured(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(emb.asyncio, "sleep", clock.sleep)
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return quota_error("EmbedContentRequestsPerMinutePerProjectPerModel-FreeTier") if calls == 1 \
            else ok_response(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    embedder = GeminiEmbedder(KEY, "m", 4, client=client, clock=clock)
    await embedder.embed_queries(["q"])
    assert 7.0 in clock.sleeps


async def test_daily_quota_is_not_retried():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return quota_error("EmbedContentRequestsPerDayPerProjectPerModel-FreeTier")

    with pytest.raises(EmbeddingError, match="daily"):
        await make(handler).embed_documents(["x"])
    assert calls == 1
