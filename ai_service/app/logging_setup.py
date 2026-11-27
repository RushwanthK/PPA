"""Application logging for the AI service: structured, correlated and safe to ship.

What it gives you
- One line per request ("request finished") with method, route, status and duration,
  plus a request id that is also returned to the caller in the X-Request-ID header
  and stored in the audit table. Search the logs for the id to see everything that
  happened in that request.
- Readable text locally (`AI_LOG_FORMAT=text`), one JSON object per line in
  production (`json`), which Render's log viewer and log tools can filter by field.

What it never writes (privacy by design, not by remembering)
- Extra fields pass through an ALLOWLIST. A field that is not listed is dropped, so a
  future `log.info(..., extra={"question": q})` cannot leak a question by accident.
- No user identity: logs carry the request id only. The audit table (in the database,
  with tighter access) links a request id to a user when that is really needed.
- No question or answer text, financial values, tokens, API keys, emails or IP
  addresses. Messages and tracebacks pass through REDACTIONS as a second safety net.
- uvicorn's own access log is turned off: it prints the client IP and full URL.
"""

import contextvars
import json
import logging
import re
import secrets
import sys
import time
from datetime import datetime, timezone

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

ALLOWED_FIELDS = frozenset({
    # request
    "request_id", "method", "route", "status", "duration_ms",
    # assistant outcome (counts and labels only, never content)
    "event", "mode", "outcome", "provider", "model", "finish_reason", "prompt_version",
    "input_tokens", "output_tokens", "latency_ms", "top_similarity", "sources", "tools", "tool_calls",
    # failures and quotas
    "error_type", "status_code", "retry_after", "daily", "remaining_requests", "limit_requests",
    "remaining_tokens", "limit_tokens",
})

# Second line of defence for text we do not fully control (provider error messages,
# exception text). Order matters: specific patterns first.
REDACTIONS = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"), "[JWT]"),
    (re.compile(r"\bgsk_[A-Za-z0-9]{10,}"), "[GROQ_KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "[GOOGLE_KEY]"),
    (re.compile(r"(?i)\b(api[_-]?key|token|password|secret)=([^&\s]+)"), r"\1=[REDACTED]"),
    (re.compile(r"postgres(?:ql)?://[^\s]+"), "postgresql://[REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"\borg_[A-Za-z0-9]{6,}"), "org_[REDACTED]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
]

_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {"message", "asctime"}
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def new_request_id() -> str:
    return secrets.token_hex(8)


def safe_fields(record: logging.LogRecord) -> dict:
    """The allowlisted extra fields of a record (everything else is dropped)."""
    return {k: v for k, v in vars(record).items() if k in ALLOWED_FIELDS and k not in _RESERVED}


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            **safe_fields(record),
        }
        if record.exc_info:
            entry["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            entry["traceback"] = redact(self.formatException(record.exc_info))
        return json.dumps(entry, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Local development: '12:01:02 INFO  ppa_ai.assistant [3f2a..] assistant request | outcome=answered ...'"""

    def format(self, record: logging.LogRecord) -> str:
        fields = safe_fields(record)
        request_id = fields.pop("request_id", "-")
        extras = " ".join(f"{k}={v}" for k, v in fields.items())
        line = (f"{time.strftime('%H:%M:%S', time.localtime(record.created))} {record.levelname:<7} "
                f"{record.name} [{request_id}] {redact(record.getMessage())}")
        if extras:
            line += f" | {extras}"
        if record.exc_info:
            line += "\n" + redact(self.formatException(record.exc_info))
        return line


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Install one stderr handler on the root logger. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    handler.addFilter(_RequestIdFilter())
    handler._ppa_ai = True  # marks our handler so a second call replaces it

    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not getattr(h, "_ppa_ai", False)]
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn's startup/error messages go through our handler (same format, redacted).
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    # uvicorn's access log prints the client IP and full URL; our middleware replaces it.
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
    access.disabled = True
    # httpx logs every outgoing URL at INFO (Gemini URLs name the model, harmless, but noisy).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
