"""Per-user usage limits and the audit log.

- Daily quota (requests and tokens) lives in Postgres, so it survives restarts and
  works across several service instances.
- The per-minute limit is in memory: cheap, and good enough for one instance. With
  several instances it would move to Redis (as Flask's rate limits already do).
- The quota day follows the Gemini free tier's reset (midnight Pacific time) and is
  shown to users in IST. See quota_clock.py.
"""

import hashlib
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date

import asyncpg

from ..logging_setup import request_id_var
from .quota_clock import format_ist, next_reset, quota_day, seconds_until_reset


class QuotaExceeded(Exception):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class Reservation:
    day: date          # the quota day the request was counted on; later updates use the same day
    requests_used: int
    tokens_used: int


class UsageStore:
    def __init__(self, pool: asyncpg.Pool, *, daily_requests: int, daily_tokens: int,
                 enforce: bool = True, provider_daily_tokens: int = 200000):
        self._pool = pool
        self.daily_requests = daily_requests
        self.daily_tokens = daily_tokens
        self.enforce = enforce                              # False: count, but never refuse
        self.provider_daily_tokens = provider_daily_tokens  # Groq's free daily tokens (whole account)

    async def reserve(self, user_id: int) -> Reservation:
        """Atomically count one request, or raise if today's limit is reached.

        A single INSERT ... ON CONFLICT DO UPDATE ... WHERE avoids the race of
        "read count, then write count + 1" under concurrent requests.
        """
        day = quota_day()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ai.usage_daily AS u (user_id, day, requests) VALUES ($1, $2, 1)
                ON CONFLICT (user_id, day) DO UPDATE SET requests = u.requests + 1
                    WHERE u.requests < $3 AND u.input_tokens + u.output_tokens < $4
                RETURNING requests, input_tokens + output_tokens AS tokens
                """,
                user_id, day,
                self.daily_requests if self.enforce else 2**31 - 1,
                self.daily_tokens if self.enforce else 2**31 - 1,   # the columns are int4
            )
        if row is None:
            raise QuotaExceeded(f"You have reached today's assistant limit. It resets at {format_ist(next_reset())}.",
                                seconds_until_reset())
        return Reservation(day, row["requests"], row["tokens"])

    async def release(self, user_id: int, day: date) -> None:
        """Give a request back when we, not the user, failed (every provider was unavailable)."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE ai.usage_daily SET requests = requests - 1 WHERE user_id = $1 AND day = $2 AND requests > 0",
                user_id, day,
            )

    async def add_tokens(self, user_id: int, day: date, input_tokens: int, output_tokens: int) -> None:
        if not (input_tokens or output_tokens):
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE ai.usage_daily SET input_tokens = input_tokens + $3, output_tokens = output_tokens + $4
                WHERE user_id = $1 AND day = $2
                """,
                user_id, day, input_tokens, output_tokens,
            )

    async def today(self, user_id: int) -> dict:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT requests, input_tokens, output_tokens FROM ai.usage_daily WHERE user_id = $1 AND day = $2",
                user_id, quota_day(),
            )
            account_tokens = await conn.fetchval(
                "SELECT COALESCE(SUM(input_tokens + output_tokens), 0) FROM ai.usage_daily WHERE day = $1",
                quota_day(),
            )
        requests = row["requests"] if row else 0
        tokens = (row["input_tokens"] + row["output_tokens"]) if row else 0
        # The budget the user is really up against: PPA's own per-user cap when it is on;
        # with the caps off, Groq's free daily tokens, which all users share.
        if self.enforce:
            budget_used, budget, source = tokens, self.daily_tokens, "ppa_daily_cap"
        else:
            budget_used, budget, source = int(account_tokens), self.provider_daily_tokens, "groq_free_tier"
        return {
            "requests_used": requests,
            "requests_limit": self.daily_requests,
            "tokens_used": tokens,
            "tokens_limit": self.daily_tokens,
            "resets_at": next_reset(),
            "limits_enforced": self.enforce,
            "token_budget": budget,
            "token_budget_used": budget_used,
            "token_budget_left_pct": max(0, round(100 - budget_used * 100 / budget)) if budget else 0,
            "token_budget_source": source,
        }


@dataclass
class AuditRecord:
    user_id: int
    outcome: str
    question: str
    latency_ms: int
    sources: list[str] = field(default_factory=list)
    top_similarity: float | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str | None = None
    mode: str = "help"
    tools: list[str] = field(default_factory=list)
    # One entry per model call (Nov 27): purpose, provider, tokens, time, ok/status.
    trips: list[dict] = field(default_factory=list)
    request_id: str = field(default_factory=request_id_var.get)


async def write_audit(pool: asyncpg.Pool, record: AuditRecord) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ai.audit_log (user_id, outcome, question_sha256, question_chars, sources,
                                      top_similarity, provider, model, prompt_version,
                                      input_tokens, output_tokens, latency_ms, finish_reason,
                                      mode, tools, request_id, trips)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17::jsonb)
            """,
            record.user_id, record.outcome,
            hashlib.sha256(record.question.encode("utf-8")).hexdigest(), len(record.question),
            record.sources, record.top_similarity, record.provider, record.model, record.prompt_version,
            record.input_tokens, record.output_tokens, record.latency_ms, record.finish_reason,
            record.mode, record.tools, record.request_id, json.dumps(record.trips),
        )


class PerMinuteLimiter:
    """Rejects (does not wait) once a user has made `limit` requests in the last 60 seconds."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[int, deque[float]] = defaultdict(deque)

    def check(self, user_id: int) -> None:
        now = self._clock()
        hits = self._hits[user_id]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            raise QuotaExceeded("Too many questions in a short time. Please wait a moment.", retry_after)
        hits.append(now)
