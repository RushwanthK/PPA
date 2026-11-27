"""The assistant's request pipeline: quota -> guardrails -> retrieve -> generate -> verify.

Each stage can end the request early, and the cheap stages come first: a refused or
off-topic question never reaches a paid model call.

    question
      | 1. per-minute + daily quota (atomic)          -> 429
      | 2. normalise, injection / advice checks        -> refusal, 0 tokens
      | 3. hybrid retrieval                             -> best similarity < threshold: "not covered", 0 tokens
      | 4. fit chunks into the context budget
      | 5. LLM (Groq, fallback Gemini), capped output   -> both down: 503
      | 6. verify: marker / valid citations required    -> otherwise "not covered"
      v
    answer + citations + disclaimer (+ notice if cut short), usage recorded, audit row written

"My data" mode (mode="my_data") shares steps 1-2 and the bookkeeping, then hands over
to DataAgent (data_agent.py): Groq-only tool calling over the user's own PPA data.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import asyncpg

from ..config import Settings
from ..llm.base import ChatModel, LLMError, Message
from ..rag.chunking import estimate_tokens
from ..rag.embeddings import Embedder, EmbeddingError
from ..rag.retrieval import RetrievedChunk, retrieve
from . import guardrails as g
from .page_links import navigation_answer, navigation_request, page_links
from .prompts import INSUFFICIENT_MARKER, PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from .quota_clock import seconds_until_reset
from .usage import AuditRecord, PerMinuteLimiter, UsageStore, write_audit

if TYPE_CHECKING:
    from .data_agent import DataAgent

log = logging.getLogger("ppa_ai.assistant")

Outcome = Literal["answered", "insufficient_context", "refused_advice", "refused_scope",
                  "ungrounded_blocked", "llm_unavailable", "figures_only", "not_my_data",
                  "navigation"]   # Nov 27: "link to / open <page>", answered by code with no model call
Mode = Literal["help", "my_data"]

CITATION_RE = re.compile(r"\[S(\d+)\]")


class AssistantUnavailable(Exception):
    """No provider could answer right now. `retry_after` is the shortest wait the
    providers told us about (seconds), or None when they did not say."""

    def __init__(self, retry_after: int | None = None):
        super().__init__("assistant unavailable")
        self.retry_after = retry_after


def _wait_for(exc: LLMError | EmbeddingError) -> int | None:
    """How long until the provider should work again, if we know."""
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        return max(1, int(retry_after + 0.999))
    if exc.daily:
        return seconds_until_reset()  # Gemini's daily limits reset at midnight Pacific
    return None


@dataclass
class Citation:
    id: str
    source_path: str
    title: str
    section: str


@dataclass
class AskResult:
    answer: str
    outcome: Outcome
    citations: list[Citation] = field(default_factory=list)
    disclaimer: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    notice: str | None = None          # e.g. the answer was cut short at the output limit
    data: list[Any] = field(default_factory=list)  # my-data mode: the DataBlocks the answer is based on
    links: list[str] = field(default_factory=list)  # help mode: page actions for "Click here" links (page_links.py)


def fit_to_budget(chunks: list[RetrievedChunk], max_tokens: int) -> list[RetrievedChunk]:
    """Keep chunks in rank order until the context budget is used. Always keep the best one."""
    kept, used = [], 0
    for c in chunks:
        cost = estimate_tokens(c.heading + c.content) + 20  # + tag overhead
        if kept and used + cost > max_tokens:
            break
        kept.append(c)
        used += cost
    return kept


_ZERO_WIDTH_RE = re.compile("[​‌‍⁠﻿]")
_LOOSE_CITATION_RE = re.compile(r"[\[【]\s*(S\s*\d+(?:\s*[,;]\s*S\s*\d+)*)\s*[\]】]")


def normalize_citations(text: str) -> str:
    """Models format citations loosely: '[​S1]' (zero-width space, seen from gpt-oss),
    '【S1】', '[S1, S2]', '[ S 3 ]'. Rewrite them all to the strict '[S1][S2]' form."""
    text = _ZERO_WIDTH_RE.sub("", text)

    def rewrite(match: re.Match) -> str:
        ids = re.findall(r"S\s*(\d+)", match.group(1))
        return "".join(f"[S{i}]" for i in ids)

    return _LOOSE_CITATION_RE.sub(rewrite, text)


def verify_citations(text: str, chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    """Keep only citations that point at a source we actually sent; remove invented ones."""
    text = normalize_citations(text)
    valid_ids = {f"S{i}" for i in range(1, len(chunks) + 1)}
    cited: list[str] = []

    def keep(match: re.Match) -> str:
        sid = f"S{match.group(1)}"
        if sid in valid_ids:
            if sid not in cited:
                cited.append(sid)
            return match.group(0)
        return ""

    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", CITATION_RE.sub(keep, text)).strip()
    citations = []
    for sid in cited:
        c = chunks[int(sid[1:]) - 1]
        citations.append(Citation(sid, c.source_path, c.title, c.heading))
    return cleaned, citations


class AssistantService:
    def __init__(self, pool: asyncpg.Pool, embedder: Embedder, chat: ChatModel, settings: Settings,
                 *, usage: UsageStore | None = None, per_minute: PerMinuteLimiter | None = None,
                 data_agent: "DataAgent | None" = None):
        self.pool = pool
        self.embedder = embedder
        self.chat = chat
        self.settings = settings
        self.usage = usage or UsageStore(pool, daily_requests=settings.daily_request_limit,
                                         daily_tokens=settings.daily_token_limit,
                                         enforce=settings.limits_enabled,
                                         provider_daily_tokens=settings.groq_daily_tokens)
        self.per_minute = per_minute or PerMinuteLimiter(settings.requests_per_minute)
        self.data_agent = data_agent

    async def ask(self, user_id: int, raw_question: str, category: str | None = None, *,
                  mode: Mode = "help", token: str | None = None,
                  history: list[tuple[str, str]] | None = None) -> AskResult:
        started = time.perf_counter()
        question = g.normalize_question(raw_question, self.settings.question_max_chars)  # may raise InvalidQuestion

        # 1. Limits first, so abuse is cheap to reject.
        self.per_minute.check(user_id)
        reservation = await self.usage.reserve(user_id)

        audit = AuditRecord(user_id=user_id, outcome="error", question=question, latency_ms=0,
                            prompt_version=PROMPT_VERSION, mode=mode)
        try:
            refusal = self._precheck(question, audit)
            if refusal is not None:
                result = refusal
            elif mode == "help" and (navigation := navigation_request(question)):
                # "Can you provide a link to the dashboard page?": no search, no model, no tokens.
                audit.outcome = "navigation"
                result = AskResult(navigation_answer(navigation), "navigation", links=navigation)
            elif mode == "my_data":
                if self.data_agent is None or not token:
                    raise AssistantUnavailable()  # needs a Groq key; Gemini is never used for personal data
                result = await self.data_agent.answer(question, token, audit, self._clean_history(history))
            else:
                result = await self._answer(question, category, audit)
        except AssistantUnavailable:
            audit.outcome = "llm_unavailable"
            raise
        finally:
            audit.latency_ms = int((time.perf_counter() - started) * 1000)
            try:
                await self.usage.add_tokens(user_id, reservation.day, audit.input_tokens, audit.output_tokens)
                if audit.outcome == "llm_unavailable":
                    # Our failure, not the user's: don't charge them a request for it.
                    await self.usage.release(user_id, reservation.day)
                await write_audit(self.pool, audit)
            except (OSError, asyncpg.PostgresError):
                # Bookkeeping must not turn an answered question into an error.
                log.exception("Failed to record usage/audit")
            log_request(audit)
        return result

    def _clean_history(self, history: list[tuple[str, str]] | None) -> list[tuple[str, str]]:
        """Earlier turns sent by the browser (my-data mode only). They go through the same
        cleanup as a question; if any earlier question looks like an injection attempt,
        all history is dropped rather than refusing the new question."""
        cleaned = []
        for q, a in (history or [])[-3:]:
            try:
                q = g.normalize_question(q, self.settings.question_max_chars)
            except g.InvalidQuestion:
                continue
            if g.looks_like_injection(q):
                log.info("Dropped chat history that looked like an injection attempt")
                return []
            cleaned.append((q, " ".join(str(a).split())))
        return cleaned

    @staticmethod
    def _precheck(question: str, audit: AuditRecord) -> AskResult | None:
        """2. Deterministic guardrails (zero tokens), for both modes."""
        if g.looks_like_injection(question):
            audit.outcome = "refused_scope"
            return AskResult(g.REFUSAL_SCOPE, "refused_scope")
        if g.asks_for_investment_advice(question):
            audit.outcome = "refused_advice"
            return AskResult(g.REFUSAL_ADVICE, "refused_advice")
        return None

    async def _answer(self, question: str, category: str | None, audit: AuditRecord) -> AskResult:
        # 3. Retrieval, and the relevance gate (zero LLM tokens when nothing is relevant).
        try:
            chunks = await retrieve(self.pool, self.embedder, question, top_k=self.settings.retrieval_top_k,
                                    category=category, keyword_weight=self.settings.keyword_weight)
        except EmbeddingError as exc:
            log.warning("Query embedding failed: %s", exc)
            raise AssistantUnavailable(_wait_for(exc)) from exc
        top_similarity = max((c.vector_similarity or 0.0 for c in chunks), default=0.0)
        audit.top_similarity = top_similarity
        if not chunks or top_similarity < self.settings.min_relevance:
            audit.outcome = "insufficient_context"
            return AskResult(g.INSUFFICIENT, "insufficient_context")

        # 4. Context budget.
        chunks = fit_to_budget(chunks, self.settings.context_max_tokens)
        audit.sources = [c.source_path for c in chunks]

        # 5. Generation.
        messages = [Message("system", SYSTEM_PROMPT), Message("user", build_user_message(question, chunks))]
        try:
            llm = await self.chat.complete(messages, max_tokens=self.settings.answer_max_tokens, temperature=0.2)
        except LLMError as exc:
            log.warning("All providers failed: %s", exc)
            raise AssistantUnavailable(_wait_for(exc)) from exc
        audit.provider, audit.model = llm.provider, llm.model
        audit.finish_reason = llm.finish_reason
        audit.input_tokens, audit.output_tokens = llm.input_tokens, llm.output_tokens

        base = dict(provider=llm.provider, model=llm.model,
                    input_tokens=llm.input_tokens, output_tokens=llm.output_tokens)

        # 6. Verify before returning anything.
        if not llm.text or INSUFFICIENT_MARKER in llm.text:
            audit.outcome = "insufficient_context"
            return AskResult(g.INSUFFICIENT, "insufficient_context", **base)
        answer, citations = verify_citations(llm.text, chunks)
        if not citations:
            # The model answered without pointing at any source: treat as ungrounded.
            log.warning("Blocked an answer without valid citations (finish=%s)", llm.finish_reason)
            audit.outcome = "ungrounded_blocked"
            return AskResult(g.INSUFFICIENT, "ungrounded_blocked", **base)

        uses_finance = any(c.source_path.startswith("finance/") for c in citations)
        audit.outcome = "answered"
        audit.sources = [c.source_path for c in citations]
        # The provider stopped at ANSWER_MAX_TOKENS: the answer is real but may be incomplete.
        notice = g.TRUNCATED_NOTICE if llm.finish_reason == "length" else None
        return AskResult(answer, "answered", citations,
                         disclaimer=g.FINANCE_DISCLAIMER if uses_finance else None, notice=notice,
                         links=page_links(question, citations), **base)


def log_request(audit: AuditRecord) -> None:
    """One summary line per question: labels and counts only. Never the question,
    the answer, user identity or any financial value (logging_setup drops other fields)."""
    level = logging.WARNING if audit.outcome in ("error", "llm_unavailable", "ungrounded_blocked") else logging.INFO
    log.log(level, "assistant request", extra={
        "event": "ask", "mode": audit.mode, "outcome": audit.outcome, "provider": audit.provider,
        "model": audit.model, "finish_reason": audit.finish_reason, "prompt_version": audit.prompt_version,
        "input_tokens": audit.input_tokens, "output_tokens": audit.output_tokens, "latency_ms": audit.latency_ms,
        "top_similarity": round(audit.top_similarity, 3) if audit.top_similarity is not None else None,
        "sources": len(audit.sources), "tools": audit.tools,
    })
