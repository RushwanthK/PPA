"""Rate limiting for the authentication endpoints (Flask-Limiter).

Why this exists
---------------
* Brute force: without limits, /login accepts unlimited password guesses.
* CPU protection: every password check runs PBKDF2-SHA256 with 1,000,000
  iterations (~0.4 s of CPU). The app runs a single Gunicorn worker, so a
  flood of login attempts blocks the whole API. Limits are evaluated in a
  before_request hook, i.e. BEFORE the view runs and before any hashing.
* Abuse/cost: /register creates database rows on the free Supabase tier.

Keys
----
* Per client IP: request.remote_addr. ProxyFix (see apply_proxy_fix) must
  already have replaced it with the real client IP when running behind
  Render's proxy; otherwise all users would share one bucket.
* Per account: a SHA-256 digest of the submitted username. Hashing keeps Redis
  keys short and fixed-length even when an attacker submits huge or unusual
  usernames, and avoids storing usernames in plain text in Redis.

Storage
-------
Counters live in the existing Redis under the "ppa:ratelimit" prefix, with an
expiry on every key. If Redis is unreachable, Flask-Limiter falls back to
per-process memory with the same limits (see config.py for the trade-offs).
"""

import hashlib
import math
import time

from flask import current_app, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix


def client_ip_key():
    """Rate-limit key for the client's IP address."""
    return f"ip:{get_remote_address()}"


limiter = Limiter(key_func=client_ip_key)


def login_username_key():
    """Rate-limit key for the account named in the login request body."""
    data = request.get_json(silent=True)
    name = data.get("name") if isinstance(data, dict) else None

    if not isinstance(name, str):
        name = ""

    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:32]
    return f"user:{digest}"


def is_failed_login(response):
    """Only wrong-credential responses count against the account limit."""
    return response.status_code == 401


def account_path_key():
    """Rate-limit key for the account in the URL (/users/<id>).

    Limits are checked before the view (and before jwt_required), so the JWT
    identity is not available yet. The URL id works because the view rejects
    any id other than the caller's own before checking a password.
    """
    account_id = (request.view_args or {}).get("id")
    return f"account:{account_id}"


def is_failed_password_check(response):
    """Only wrong current-password attempts count (set by the view)."""
    return bool(g.get("password_check_failed", False))


# Limits are read from config at request time, so they can be changed with
# environment variables without code changes.
def login_rate_limit():
    return current_app.config["LOGIN_RATE_LIMIT"]


def login_failure_rate_limit():
    return current_app.config["LOGIN_FAILURE_RATE_LIMIT"]


def register_rate_limit():
    return current_app.config["REGISTER_RATE_LIMIT"]


def password_change_failure_rate_limit():
    return current_app.config["PASSWORD_CHANGE_FAILURE_RATE_LIMIT"]


LOGIN_IP_MESSAGE = "Too many login attempts from this network."
LOGIN_ACCOUNT_MESSAGE = "Too many failed login attempts for this account."
REGISTER_IP_MESSAGE = "Too many registration attempts from this network."
PASSWORD_CHANGE_MESSAGE = "Too many incorrect current-password attempts."


def apply_proxy_fix(app):
    """Trust exactly TRUSTED_PROXY_COUNT proxies for X-Forwarded-For.

    ProxyFix(x_for=N) takes the Nth value from the RIGHT of X-Forwarded-For,
    i.e. the address appended by the outermost trusted proxy. Values further
    left were supplied by the client and are ignored, so a client cannot
    choose its own rate-limit bucket by sending a fake header.
    """
    count = int(app.config.get("TRUSTED_PROXY_COUNT", 0))

    if count > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=count)


# Headers that reverse proxies / CDNs commonly add with the client address.
_PROXY_HEADERS = (
    "X-Forwarded-For",
    "X-Real-IP",
    "True-Client-IP",
    "CF-Connecting-IP",
    "X-Forwarded-Proto",
)


def log_proxy_headers():
    """Log what the proxies in front of Flask send (PROXY_DIAGNOSTICS only).

    Used once to choose TRUSTED_PROXY_COUNT: request GET / with a fake
    X-Forwarded-For value and see where the fake value and the real client
    IP end up in the list. Only GET / is logged (the frontend never calls it),
    and header values are truncated so the log line stays small.
    """
    if not current_app.config.get("PROXY_DIAGNOSTICS", False):
        return
    if request.method != "GET" or request.path != "/":
        return

    # ProxyFix (when enabled) rewrites REMOTE_ADDR and keeps the original here.
    original = request.environ.get("werkzeug.proxy_fix.orig", {})
    socket_peer = original.get("REMOTE_ADDR", request.environ.get("REMOTE_ADDR"))

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    entries = [part.strip() for part in forwarded_for.split(",") if part.strip()]

    details = {
        "socket_peer": socket_peer,
        "remote_addr_used": request.remote_addr,
        "trusted_proxy_count": current_app.config.get("TRUSTED_PROXY_COUNT", 0),
        "x_forwarded_for_entries": len(entries),
    }
    for name in _PROXY_HEADERS:
        value = request.headers.get(name)
        if value is not None:
            details[name] = value[:300]

    current_app.logger.warning("ppa_proxy_diagnostics %s", details)


def _format_wait(seconds):
    if seconds < 60:
        unit = "second" if seconds == 1 else "seconds"
        return f"{seconds} {unit}"

    minutes = math.ceil(seconds / 60)
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit}"


def rate_limit_exceeded(error):
    """JSON 429 response; LoginPage already displays the "error" field."""
    retry_after = None

    try:
        current = limiter.current_limit
        if current is not None:
            retry_after = max(1, int(current.reset_at - time.time()))
    except Exception:  # pragma: no cover - storage failure while reporting
        retry_after = None

    message = error.description or "Too many requests."

    if retry_after is not None:
        message = f"{message} Please try again in {_format_wait(retry_after)}."

    body = {"error": message}

    if retry_after is not None:
        body["retry_after"] = retry_after

    return jsonify(body), 429


def init_rate_limiting(app):
    apply_proxy_fix(app)
    app.before_request(log_proxy_headers)
    limiter.init_app(app)
    app.register_error_handler(RateLimitExceeded, rate_limit_exceeded)
