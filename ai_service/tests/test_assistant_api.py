"""HTTP layer: authentication, status codes and response shape. The service and the
Flask auth call are replaced with fakes."""

from datetime import datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from app.assistant import routes
from app.assistant.auth import AuthError, AuthUnavailable, CurrentUser, FlaskAuthClient
from app.assistant.guardrails import InvalidQuestion
from app.assistant.service import AskResult, AssistantUnavailable, Citation
from app.assistant.usage import QuotaExceeded
from app.config import Settings
from app.main import create_app

TOKEN = "header.payload.signature"


class FakeAuth:
    def __init__(self, error=None):
        self.error, self.tokens = error, []

    async def verify(self, token):
        self.tokens.append(token)
        if self.error:
            raise self.error
        return CurrentUser(42)


class FakeUsage:
    async def today(self, user_id):
        return {"requests_used": 3, "requests_limit": 50, "tokens_used": 900, "tokens_limit": 60000,
                "resets_at": datetime.fromisoformat("2026-11-25T13:30:00+05:30")}


class FakeAssistant:
    usage = FakeUsage()

    def __init__(self, result=None, error=None):
        self.result, self.error, self.calls = result, error, []

    async def ask(self, user_id, question, category=None, **kwargs):
        self.calls.append((user_id, question, category, *kwargs.items()) if kwargs else (user_id, question, category))
        if self.error:
            raise self.error
        return self.result


ANSWER = AskResult("Use the card page [S1].", "answered",
                   [Citation("S1", "ppa/04-credit-cards.md", "Credit cards in PPA", "Credit cards in PPA > Recording a payment")],
                   None, "groq", "openai/gpt-oss-120b", 812, 95)


def make_client(assistant=None, auth=None, **settings):
    app = create_app(Settings(_env_file=None, AI_ENV="test", **settings))
    app.dependency_overrides[routes.get_auth_client] = lambda: auth or FakeAuth()
    if assistant is not None:
        app.dependency_overrides[routes.get_assistant] = lambda: assistant
    return TestClient(app)


def ask(client, body=None, token=TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/v1/ask", json=body or {"question": "How do I pay my card?"}, headers=headers)


def test_successful_answer_shape():
    assistant = FakeAssistant(ANSWER)
    with make_client(assistant) as client:
        response = ask(client, {"question": "How do I pay my card?", "category": "ppa"})
    assert response.status_code == 200
    assert response.json() == {
        "answer": "Use the card page [S1].",
        "outcome": "answered",
        "citations": [{"id": "S1", "source_path": "ppa/04-credit-cards.md", "title": "Credit cards in PPA",
                       "section": "Credit cards in PPA > Recording a payment"}],
        "disclaimer": None,
        "notice": None,
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "usage": {"input_tokens": 812, "output_tokens": 95},
        "data": [],
        "links": [],   # help-mode page actions (page_links.py); none from this fake
    }
    assert assistant.calls == [(42, "How do I pay my card?", "ppa")]  # user id comes from the token


@pytest.mark.parametrize("header", [None, "Basic abc", "Bearer ", "Token abc"])
def test_missing_or_malformed_authorization_is_401(header):
    with make_client(FakeAssistant(ANSWER)) as client:
        headers = {"Authorization": header} if header else {}
        response = client.post("/v1/ask", json={"question": "hi there"}, headers=headers)
    assert response.status_code == 401
    assert response.json() == {"error": "Please log in to continue."}


def test_invalid_token_is_401():
    with make_client(FakeAssistant(ANSWER), FakeAuth(AuthError())) as client:
        assert ask(client).status_code == 401


def test_auth_service_down_fails_closed_with_503():
    assistant = FakeAssistant(ANSWER)
    with make_client(assistant, FakeAuth(AuthUnavailable())) as client:
        response = ask(client)
    assert response.status_code == 503 and assistant.calls == []


def test_kill_switch_returns_503_before_any_work():
    with make_client(auth=FakeAuth(), AI_ENABLED=False) as client:
        response = ask(client)
    assert response.status_code == 503
    assert response.json()["error"] == routes.UNAVAILABLE_MESSAGE


def test_assistant_not_configured_returns_503():
    with make_client(auth=FakeAuth(), GEMINI_API_KEY="", GROQ_API_KEY="") as client:
        assert ask(client).status_code == 503


@pytest.mark.parametrize("error,status", [
    (InvalidQuestion("Please type a question."), 400),
    (QuotaExceeded("limit"), 429),
    (AssistantUnavailable(), 503),
])
def test_service_errors_map_to_status_codes(error, status):
    with make_client(FakeAssistant(error=error)) as client:
        response = ask(client)
    assert response.status_code == status
    assert "error" in response.json()


def test_per_minute_limit_sends_retry_after():
    with make_client(FakeAssistant(error=QuotaExceeded("wait", retry_after=17))) as client:
        response = ask(client)
    assert response.status_code == 429 and response.headers["retry-after"] == "17"


def test_request_validation():
    with make_client(FakeAssistant(ANSWER)) as client:
        assert ask(client, {"question": ""}).status_code == 422
        assert ask(client, {"question": "x" * 4001}).status_code == 422
        assert ask(client, {"question": "hi there", "category": "secret"}).status_code == 422


def test_usage_endpoint():
    with make_client(FakeAssistant(ANSWER)) as client:
        response = client.get("/v1/usage", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200 and response.json()["requests_limit"] == 50


# ---- FlaskAuthClient -----------------------------------------------------------------------

def flask(handler, clock=None, ttl=30.0):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kwargs = {"clock": clock} if clock else {}
    return FlaskAuthClient("http://flask.local/", http, cache_seconds=ttl, **kwargs)


async def test_flask_auth_returns_user_and_caches():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"id": 42, "name": "x", "dob": "2000-01-01", "place": "y", "age": 1})

    auth = flask(handler)
    assert (await auth.verify(TOKEN)).id == 42
    assert (await auth.verify(TOKEN)).id == 42
    assert len(calls) == 1                                  # second call served from cache
    assert str(calls[0].url) == "http://flask.local/me"
    assert calls[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(auth._cache)                    # only a hash is kept


async def test_flask_auth_cache_expires():
    now = [0.0]
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"id": 1})

    auth = flask(handler, clock=lambda: now[0], ttl=30)
    await auth.verify(TOKEN)
    now[0] = 31
    await auth.verify(TOKEN)
    assert len(calls) == 2


@pytest.mark.parametrize("status", [401, 422])
async def test_flask_rejects_token(status):
    auth = flask(lambda r: httpx.Response(status, json={"error": "Please log in to continue."}))
    with pytest.raises(AuthError):
        await auth.verify(TOKEN)


async def test_flask_down_is_unavailable_not_unauthorized():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(AuthUnavailable):
        await flask(handler).verify(TOKEN)
    with pytest.raises(AuthUnavailable):
        await flask(lambda r: httpx.Response(500)).verify(TOKEN)


def test_unavailable_without_a_known_wait_uses_the_generic_message():
    with make_client(FakeAssistant(error=AssistantUnavailable())) as client:
        response = ask(client)
    assert response.status_code == 503
    assert response.json()["error"] == routes.UNAVAILABLE_MESSAGE
    assert "retry-after" not in response.headers


def test_unavailable_for_a_short_wait_says_busy():
    with make_client(FakeAssistant(error=AssistantUnavailable(retry_after=40))) as client:
        response = ask(client)
    assert response.status_code == 503 and response.headers["retry-after"] == "40"
    assert response.json()["error"] == "The assistant is busy right now. Please try again in about 40 seconds."


def test_unavailable_for_a_long_wait_names_the_ist_time():
    with make_client(FakeAssistant(error=AssistantUnavailable(retry_after=5 * 3600))) as client:
        response = ask(client)
    message = response.json()["error"]
    assert response.status_code == 503 and response.headers["retry-after"] == "18000"
    assert message.startswith("The assistant has reached its daily limit") and "IST" in message


def test_cut_off_notice_is_returned():
    result = AskResult("Partial answer [S1].", "answered", ANSWER.citations, notice="cut short")
    with make_client(FakeAssistant(result)) as client:
        assert ask(client).json()["notice"] == "cut short"


def test_usage_reports_the_reset_time_in_ist():
    with make_client(FakeAssistant(ANSWER)) as client:
        body = client.get("/v1/usage", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert body["resets_at"] == "2026-11-25T13:30:00+05:30"


# ---- My-data mode ------------------------------------------------------------------------

def test_my_data_mode_passes_the_token_and_returns_the_figures():
    from app.assistant.tools import DataBlock, Table
    block = DataBlock("Accounts (now)", {"bank_accounts": 1}, [Table("Bank accounts", ["name", "balance"],
                                                                     [["HDFC", 81234.5]])])
    result = AskResult("Your HDFC balance is ₹81,234.50.", "answered", provider="groq",
                       model="openai/gpt-oss-120b", input_tokens=900, output_tokens=80, data=[block])
    assistant = FakeAssistant(result)
    with make_client(assistant) as client:
        response = ask(client, {"question": "What is my bank balance?", "mode": "my_data", "category": "ppa"})
    assert response.status_code == 200
    assert response.json()["data"] == [{"title": "Accounts (now)", "facts": {"bank_accounts": 1},
                                        "tables": [{"title": "Bank accounts", "columns": ["name", "balance"],
                                                    "rows": [["HDFC", 81234.5]]}]}]
    assert assistant.calls == [(42, "What is my bank balance?", None, ("mode", "my_data"), ("token", TOKEN),
                                ("history", []))]


def test_token_revoked_during_my_data_is_401():
    from app.assistant.flask_data import DataAuthError
    with make_client(FakeAssistant(error=DataAuthError())) as client:
        response = ask(client, {"question": "my balance?", "mode": "my_data"})
    assert response.status_code == 401 and response.json() == {"error": routes.LOGIN_MESSAGE}


def test_unknown_mode_is_422():
    with make_client(FakeAssistant(ANSWER)) as client:
        assert ask(client, {"question": "my balance?", "mode": "sql"}).status_code == 422


def test_my_data_history_is_passed_on_and_limited():
    assistant = FakeAssistant(ANSWER)
    turns = [{"question": "goa trip?", "answer": "₹4,300 all time."}]
    with make_client(assistant) as client:
        ok = ask(client, {"question": "and January?", "mode": "my_data", "history": turns})
        too_many = ask(client, {"question": "x?", "mode": "my_data", "history": turns * 4})
        too_long = ask(client, {"question": "x?", "mode": "my_data",
                                "history": [{"question": "q" * 501, "answer": "a"}]})
        help_mode = ask(client, {"question": "how do I add a card?", "history": turns})
    assert ok.status_code == 200 and too_many.status_code == 422 and too_long.status_code == 422
    assert assistant.calls[0][-1] == ("history", [("goa trip?", "₹4,300 all time.")])
    assert help_mode.status_code == 200 and assistant.calls[1] == (42, "how do I add a card?", None)
