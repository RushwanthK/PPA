"""Provider-neutral types for chat models."""

from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int          # includes hidden reasoning/thinking tokens: they are billed too
    finish_reason: str          # "stop", "length", "content_filter", ...
    latency_ms: int


class LLMError(Exception):
    """A provider call failed. `retryable` errors (rate limit, timeout, outage) may
    succeed on another provider; others (bad request) are our bug and should surface.
    Messages never contain API keys."""

    def __init__(self, message: str, *, provider: str, retryable: bool, status: int | None = None,
                 retry_after: float | None = None, daily: bool = False):
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status = status
        self.retry_after = retry_after  # seconds the provider asked us to wait, if it said
        self.daily = daily              # a per-day limit was hit (it will not recover in a minute)


class ChatModel(Protocol):
    provider: str
    model: str

    async def complete(self, messages: list[Message], *, max_tokens: int, temperature: float = 0.2) -> LLMResult: ...


def safe_error_message(response) -> str:
    try:
        return str(response.json().get("error", {}).get("message", ""))[:200]
    except (ValueError, AttributeError):
        return ""


def parse_seconds(value) -> float | None:
    """'37', '37s' or '1.5' -> seconds; anything else -> None."""
    try:
        return float(str(value).strip().rstrip("s"))
    except (TypeError, ValueError):
        return None


def google_quota_details(response) -> tuple[list[str], float | None]:
    """Google errors carry structured details: which quota was hit (QuotaFailure,
    e.g. 'GenerateRequestsPerDayPerProjectPerModel-FreeTier') and how long to wait
    (RetryInfo, e.g. '37s')."""
    quota_ids: list[str] = []
    retry_delay = None
    try:
        details = response.json().get("error", {}).get("details", [])
    except (ValueError, AttributeError):
        return quota_ids, None
    for d in details:
        kind = d.get("@type", "")
        if kind.endswith("google.rpc.QuotaFailure"):
            quota_ids += [str(v.get("quotaId", "")) for v in d.get("violations", [])]
        elif kind.endswith("google.rpc.RetryInfo"):
            retry_delay = parse_seconds(d.get("retryDelay"))
    return quota_ids, retry_delay
