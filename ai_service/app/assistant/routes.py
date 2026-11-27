"""HTTP endpoints for the assistant (version 1)."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .flask_data import DataAuthError
from .auth import AuthError, AuthUnavailable, CurrentUser, FlaskAuthClient
from .guardrails import InvalidQuestion
from .quota_clock import format_ist
from .service import AssistantService, AssistantUnavailable
from .usage import QuotaExceeded

router = APIRouter(prefix="/v1", tags=["assistant"])

# Same wording as the Flask API, so the frontend handles both services the same way.
LOGIN_MESSAGE = "Please log in to continue."
UNAVAILABLE_MESSAGE = "The assistant is temporarily unavailable. Please try again later."
BUSY_SECONDS = 120  # waits up to this long are "busy"; longer ones are a daily limit


def unavailable_error(retry_after: int | None) -> "ApiError":
    """503 that tells the user how long to wait, when the providers told us."""
    if retry_after is None:
        return ApiError(503, UNAVAILABLE_MESSAGE)
    headers = {"Retry-After": str(retry_after)}
    if retry_after <= BUSY_SECONDS:
        return ApiError(503, f"The assistant is busy right now. Please try again in about {retry_after} seconds.",
                        headers)
    resume = datetime.now(timezone.utc) + timedelta(seconds=retry_after)
    return ApiError(503, "The assistant has reached its daily limit with its AI providers. "
                         f"Please try again after {format_ist(resume)}.", headers)


class ApiError(Exception):
    def __init__(self, status: int, message: str, headers: dict | None = None):
        self.status, self.message, self.headers = status, message, headers or {}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": exc.message}, headers=exc.headers)


# ---- Dependencies (tests replace these through app.dependency_overrides) ----------

def get_auth_client(request: Request) -> FlaskAuthClient:
    return request.app.state.auth_client


_build_lock = asyncio.Lock()


async def get_assistant(request: Request) -> AssistantService:
    state = request.app.state
    if not state.settings.ai_enabled:  # kill switch
        raise ApiError(503, UNAVAILABLE_MESSAGE)
    if state.assistant is None and hasattr(state, "db"):
        # Not built at startup (for example the database was down). Try again, once at a time.
        async with _build_lock:
            if state.assistant is None:
                from .factory import build_assistant
                state.assistant = await build_assistant(state.settings, state.db, state.http)
    if state.assistant is None:
        raise ApiError(503, UNAVAILABLE_MESSAGE)
    return state.assistant


def bearer_token(request: Request) -> str:
    """The raw token, for my-data mode: tools call Flask as the user. It is kept only
    for this request: never logged, cached or stored."""
    return request.headers.get("Authorization", "").partition(" ")[2].strip()


async def current_user(request: Request, auth: FlaskAuthClient = Depends(get_auth_client)) -> CurrentUser:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, LOGIN_MESSAGE)
    try:
        return await auth.verify(token.strip())
    except AuthError:
        raise ApiError(401, LOGIN_MESSAGE) from None
    except AuthUnavailable:
        # Fail closed: if identity cannot be checked, nobody gets in.
        raise ApiError(503, UNAVAILABLE_MESSAGE) from None


# ---- Schemas ------------------------------------------------------------------------

class HistoryTurn(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    answer: str = Field(..., max_length=1000)


class AskRequest(BaseModel):
    # Hard cap at the HTTP layer; the service applies the configurable limit after cleanup.
    question: str = Field(..., min_length=1, max_length=4000)
    category: Literal["ppa", "finance"] | None = None
    # help: PPA help articles and finance notes. my_data: the user's own PPA data (Groq only).
    mode: Literal["help", "my_data"] = "help"
    # my_data only: up to 3 earlier turns of this chat, so follow-ups make sense. Kept for
    # this request only; never stored or logged. Ignored in help mode.
    history: list[HistoryTurn] = Field(default_factory=list, max_length=3)


class CitationOut(BaseModel):
    id: str
    source_path: str
    title: str
    section: str


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int


class TableOut(BaseModel):
    title: str
    columns: list[str]
    rows: list[list]


class DataBlockOut(BaseModel):
    title: str
    facts: dict
    tables: list[TableOut]


class AskResponse(BaseModel):
    answer: str
    outcome: str
    citations: list[CitationOut]
    disclaimer: str | None
    notice: str | None
    provider: str | None
    model: str | None
    usage: UsageOut
    data: list[DataBlockOut] = []  # my-data mode: the figures the answer is based on
    # help mode: action names such as "creditcard.add_transaction" (never URLs); the browser
    # maps them to its own fixed list of pages and asks which of the user's accounts.
    links: list[str] = []


class UsageTodayOut(BaseModel):
    requests_used: int
    requests_limit: int
    tokens_used: int
    tokens_limit: int
    resets_at: datetime  # IST, e.g. 2026-11-25T13:30:00+05:30 (midnight Pacific, when Gemini resets)
    # Nov 26: what the panel shows as "% of today's tokens left".
    limits_enforced: bool = True
    token_budget: int = 0
    token_budget_used: int = 0
    token_budget_left_pct: int = 0
    token_budget_source: str = "ppa_daily_cap"   # or "groq_free_tier" when the per-user caps are off


# ---- Endpoints -------------------------------------------------------------------------

@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request, user: CurrentUser = Depends(current_user),
              assistant: AssistantService = Depends(get_assistant)) -> AskResponse:
    try:
        if body.mode == "my_data":
            result = await assistant.ask(user.id, body.question, None, mode="my_data",
                                         token=bearer_token(request),
                                         history=[(t.question, t.answer) for t in body.history])
        else:
            result = await assistant.ask(user.id, body.question, body.category)
    except InvalidQuestion as exc:
        raise ApiError(400, str(exc)) from None
    except QuotaExceeded as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise ApiError(429, str(exc), headers) from None
    except AssistantUnavailable as exc:
        raise unavailable_error(exc.retry_after) from None
    except DataAuthError:
        raise ApiError(401, LOGIN_MESSAGE) from None
    return AskResponse(
        answer=result.answer,
        outcome=result.outcome,
        citations=[CitationOut(**c.__dict__) for c in result.citations],
        disclaimer=result.disclaimer,
        notice=result.notice,
        provider=result.provider,
        model=result.model,
        usage=UsageOut(input_tokens=result.input_tokens, output_tokens=result.output_tokens),
        data=[b.for_user() for b in result.data],   # figures and tables; model instructions hidden
        links=result.links,
    )


@router.get("/usage", response_model=UsageTodayOut)
async def usage_today(user: CurrentUser = Depends(current_user),
                      assistant: AssistantService = Depends(get_assistant)) -> UsageTodayOut:
    return UsageTodayOut(**await assistant.usage.today(user.id))
