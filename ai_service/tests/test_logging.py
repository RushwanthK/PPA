"""Logging: allowlisted fields, redaction, request ids, and no personal data."""

import json
import logging

from fastapi.testclient import TestClient

from app.assistant.service import log_request
from app.assistant.usage import AuditRecord
from app.config import Settings
from app.llm.groq import watch_quota
from app.logging_setup import JsonFormatter, TextFormatter, configure_logging, redact, request_id_var
from app.main import create_app


def record(msg="hello", **extra):
    rec = logging.LogRecord("ppa_ai.test", logging.INFO, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


def test_redacts_secrets_and_personal_data():
    text = ("Bearer abc.def-ghi key gsk_ABCDEFGHIJKLMNOP google AIzaSyA1234567890abcdefghijk "
            "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI0MiJ9.c2lnbmF0dXJl mail a.person@example.com "
            "ip 203.0.113.7 db postgresql://u:p@host/db api_key=xyz org org_01abcdefgh")
    out = redact(text)
    for secret in ("abc.def-ghi", "gsk_ABCDEFGHIJKLMNOP", "AIzaSy", "eyJhbGci", "a.person@example.com",
                   "203.0.113.7", "u:p@host", "api_key=xyz", "org_01abcdefgh"):
        assert secret not in out, secret
    assert "[GROQ_KEY]" in out and "[EMAIL]" in out and "[IP]" in out


def test_json_formatter_keeps_only_allowlisted_fields():
    line = JsonFormatter().format(record("assistant request", outcome="answered", input_tokens=10,
                                         question="how much did I spend", answer="₹5,000", user_id=42,
                                         request_id="abc123def456"))
    entry = json.loads(line)
    assert entry["outcome"] == "answered" and entry["input_tokens"] == 10
    assert entry["request_id"] == "abc123def456" and entry["level"] == "INFO"
    assert "question" not in entry and "answer" not in entry and "user_id" not in entry


def test_formatters_redact_exception_text():
    try:
        raise RuntimeError("failed with Bearer secret-token-value")
    except RuntimeError:
        import sys
        rec = record("boom")
        rec.exc_info = sys.exc_info()
    assert "secret-token-value" not in JsonFormatter().format(rec)
    assert "secret-token-value" not in TextFormatter().format(rec)
    assert json.loads(JsonFormatter().format(rec))["error_type"] == "RuntimeError"


def test_text_formatter_is_readable():
    line = TextFormatter().format(record("request finished", route="/v1/ask", status=200, request_id="r1d2"))
    assert "[r1d2] request finished | route=/v1/ask status=200" in line


def test_request_summary_never_contains_the_question(caplog):
    audit = AuditRecord(user_id=7, outcome="answered", question="how much did I spend at Swiggy",
                        latency_ms=120, provider="groq", tools=["summarize_transactions"], mode="my_data")
    with caplog.at_level(logging.INFO, logger="ppa_ai.assistant"):
        log_request(audit)
    rec = caplog.records[-1]
    line = JsonFormatter().format(rec)
    assert "Swiggy" not in line and '"user_id"' not in line
    assert json.loads(line)["tools"] == ["summarize_transactions"]


def test_groq_quota_warning_when_below_ten_percent(caplog):
    with caplog.at_level(logging.WARNING, logger="ppa_ai.llm"):
        watch_quota({"x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "50",
                     "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "7000"})
    assert len(caplog.records) == 1
    assert caplog.records[0].remaining_requests == 50 and caplog.records[0].limit_requests == 1000


def test_no_quota_warning_without_headers(caplog):
    with caplog.at_level(logging.WARNING, logger="ppa_ai.llm"):
        watch_quota({})
    assert caplog.records == []


def client():
    return TestClient(create_app(Settings(_env_file=None, AI_ENV="test", AI_ENABLED=False)))


def test_every_response_has_a_request_id(caplog):
    with client() as c, caplog.at_level(logging.INFO, logger="ppa_ai.request"):
        response = c.post("/v1/ask", json={"question": "hello there"})
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 16
    finished = [r for r in caplog.records if r.getMessage() == "request finished"][-1]
    assert finished.route == "/v1/ask" and finished.status == 401 and finished.request_id == request_id
    assert request_id_var.get() == "-"  # reset after the request


def test_valid_incoming_request_id_is_reused_and_bad_one_replaced():
    with client() as c:
        assert c.get("/health/live", headers={"X-Request-ID": "proxy-id-12345"}).headers["X-Request-ID"] \
            == "proxy-id-12345"
        replaced = c.get("/health/live", headers={"X-Request-ID": "bad id\nINJECTED"}).headers["X-Request-ID"]
    assert "INJECTED" not in replaced and len(replaced) == 16


def test_unknown_paths_are_not_logged_verbatim(caplog):
    with client() as c, caplog.at_level(logging.INFO, logger="ppa_ai.request"):
        c.get("/some/path/with/a.person@example.com")
    finished = [r for r in caplog.records if r.getMessage() == "request finished"][-1]
    assert finished.route == "unmatched"


def test_uvicorn_access_log_is_disabled():
    configure_logging("INFO", "text")
    assert logging.getLogger("uvicorn.access").disabled


def test_log_format_defaults_by_environment():
    assert Settings(_env_file=None, AI_ENV="production").log_format == "json"
    assert Settings(_env_file=None, AI_ENV="development").log_format == "text"
    assert Settings(_env_file=None, AI_ENV="development", AI_LOG_FORMAT="json").log_format == "json"


# ---- CORS (step 5: the React chat panel calls this service from the browser) -------------

def test_cors_allows_the_configured_origin_only():
    app = create_app(Settings(_env_file=None, AI_ENV="test", AI_ENABLED=False))
    with TestClient(app) as c:
        ok = c.options("/v1/ask", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "authorization,content-type"})
        bad = c.options("/v1/ask", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        simple = c.get("/health/live", headers={"Origin": "http://localhost:3000"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-credentials" not in ok.headers
    assert "access-control-allow-origin" not in bad.headers
    assert "x-request-id" in simple.headers["access-control-expose-headers"].lower()


def test_cors_origins_setting_accepts_a_list():
    s = Settings(_env_file=None, AI_CORS_ORIGINS="http://localhost:3000, https://ppa.example.app/")
    assert s.cors_origin_list == ["http://localhost:3000", "https://ppa.example.app"]
