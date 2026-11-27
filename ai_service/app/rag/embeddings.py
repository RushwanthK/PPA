"""Text embeddings: the Gemini API client, plus a deterministic fake for tests.

Why a thin httpx client instead of a vendor SDK: full control over timeouts,
retries and usage accounting, one fewer heavy dependency, and an interface that
another provider can implement later.
"""

import asyncio
import hashlib
import logging
import math
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from ..llm.base import google_quota_details

log = logging.getLogger("ppa_ai.embeddings")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class EmbeddingError(Exception):
    """Embedding request failed. The message never contains the API key."""

    def __init__(self, message: str, *, daily: bool = False):
        super().__init__(message)
        self.daily = daily  # the per-day quota is used up: retrying today will not help


@dataclass
class EmbeddingUsage:
    requests: int = 0          # HTTP calls made, including retries
    texts: int = 0             # texts embedded
    estimated_tokens: int = 0  # characters / 4, for budgeting
    throttled_seconds: float = 0.0  # time spent waiting to respect the rate limit


class Embedder(Protocol):
    model: str
    dimensions: int
    usage: EmbeddingUsage

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_queries(self, texts: list[str]) -> list[list[float]]: ...


def vector_literal(values: list[float]) -> str:
    """pgvector text format, e.g. '[0.1,0.2]'. Avoids needing numpy-based codecs."""
    return "[" + ",".join(f"{v:.7g}" for v in values) + "]"


class GeminiEmbedder:
    """Calls Gemini's batchEmbedContents endpoint.

    - The API key goes in the `x-goog-api-key` header, never the URL, so it does
      not end up in proxy or access logs.
    - Documents and queries use different task types (RETRIEVAL_DOCUMENT and
      RETRIEVAL_QUERY), which the model is trained to match against each other.
    - 429 and 5xx responses are retried with exponential backoff, honoring Retry-After.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        *,
        client: httpx.AsyncClient | None = None,
        batch_size: int = 50,
        max_retries: int = 3,
        timeout: float = 30.0,
        base_url: str = GEMINI_BASE_URL,
        texts_per_minute: int = 90,
        clock=time.monotonic,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.model = model
        self.dimensions = dimensions
        self.usage = EmbeddingUsage()
        self._api_key = api_key
        # The free tier counts every text in a batch against a per-minute limit,
        # so a batch can never be larger than the per-minute budget.
        self._batch_size = max(1, min(batch_size, texts_per_minute))
        self._limiter = SlidingWindowLimiter(texts_per_minute, 60.0, clock=clock)
        self._max_retries = max_retries
        self._url = f"{base_url}/models/{model}:batchEmbedContents"
        self._client = client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "RETRIEVAL_QUERY")

    async def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            vectors.extend(await self._embed_batch(texts[start:start + self._batch_size], task_type))
        return vectors

    async def _embed_batch(self, texts: list[str], task_type: str) -> list[list[float]]:
        body = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dimensions,
                }
                for t in texts
            ]
        }
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}

        for attempt in range(self._max_retries + 1):
            # Wait for room in the per-minute budget before sending (proactive, not reactive).
            waited = await self._limiter.acquire(len(texts))
            if waited:
                self.usage.throttled_seconds += waited
                log.info("Throttled %.1fs to stay under %d embedded texts per minute",
                         waited, self._limiter.limit)
            self.usage.requests += 1
            try:
                response = await self._client.post(self._url, json=body, headers=headers)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise EmbeddingError(f"Embedding request failed ({type(exc).__name__})") from None
                await asyncio.sleep(self._backoff(attempt, None))
                continue

            if response.status_code == 200:
                vectors = [e["values"] for e in response.json().get("embeddings", [])]
                if len(vectors) != len(texts):
                    raise EmbeddingError("Embedding response had the wrong number of vectors")
                for v in vectors:
                    if len(v) != self.dimensions:
                        raise EmbeddingError(
                            f"Expected {self.dimensions} dimensions, got {len(v)}. "
                            "Check EMBEDDING_DIMENSIONS and the database column."
                        )
                self.usage.texts += len(texts)
                self.usage.estimated_tokens += sum(math.ceil(len(t) / 4) for t in texts)
                return vectors

            quota_ids, retry_delay = google_quota_details(response)
            if any("PerDay" in q for q in quota_ids):
                # A daily quota will not recover by retrying now; stop and say so.
                raise EmbeddingError("Gemini daily embedding quota is exhausted", daily=True)
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                delay = self._backoff(attempt, response.headers.get("retry-after") or (str(retry_delay) if retry_delay else None))
                log.warning("Gemini embeddings returned %s; retrying in %.1fs", response.status_code, delay)
                await asyncio.sleep(delay)
                continue
            raise EmbeddingError(f"Gemini embeddings returned HTTP {response.status_code}: {_safe_error(response)}")
        raise EmbeddingError("Embedding request failed")  # pragma: no cover

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), 60.0)
            except ValueError:
                pass
        return min(2.0 ** attempt, 30.0)


class SlidingWindowLimiter:
    """Allows at most `limit` units per `window` seconds, waiting (asynchronously) when full.

    Units here are embedded texts. A lock keeps concurrent callers from both
    seeing the same free capacity.
    """

    def __init__(self, limit: int, window: float, *, clock=time.monotonic):
        self.limit = limit
        self.window = window
        self._clock = clock
        self._events: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    def _used(self, now: float) -> int:
        while self._events and now - self._events[0][0] >= self.window:
            self._events.popleft()
        return sum(n for _, n in self._events)

    async def acquire(self, units: int) -> float:
        """Reserve capacity; returns the seconds spent waiting."""
        if units > self.limit:
            raise ValueError(f"Batch of {units} exceeds the limit of {self.limit} per window")
        waited = 0.0
        async with self._lock:
            while True:
                now = self._clock()
                if self._used(now) + units <= self.limit:
                    self._events.append((now, units))
                    return waited
                delay = self.window - (now - self._events[0][0]) + 0.05
                waited += delay
                await asyncio.sleep(delay)


def _safe_error(response: httpx.Response) -> str:
    """Provider error message (truncated). It describes the request, and never echoes the key."""
    try:
        return str(response.json().get("error", {}).get("message", ""))[:200]
    except ValueError:
        return ""


@dataclass
class FakeEmbedder:
    """Deterministic, offline embedder for tests: hashes words into buckets, so texts
    sharing words get similar vectors. Not semantic, but enough to test the pipeline."""

    dimensions: int = 768
    model: str = "fake-hash-embedder"
    usage: EmbeddingUsage = field(default_factory=EmbeddingUsage)
    calls: int = 0

    def _vector(self, text: str) -> list[float]:
        v = [0.0] * self.dimensions
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            v[h % self.dimensions] += 1.0 if (h >> 64) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.usage.requests += 1
        self.usage.texts += len(texts)
        return [self._vector(t) for t in texts]

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return await self.embed_documents(texts)
