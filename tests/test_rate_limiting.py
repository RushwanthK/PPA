"""Security regression tests for login/register rate limiting.

The limiter is disabled for the rest of the suite. The ``rate_limited``
fixture (conftest.py) switches it on with clean in-memory counters.

Limits used here come from TestingConfig:
    LOGIN_RATE_LIMIT          = "10 per minute;50 per hour"   (per client IP)
    LOGIN_FAILURE_RATE_LIMIT  = "5 per 15 minutes"             (per account, 401s only)
    REGISTER_RATE_LIMIT       = "3 per hour"                   (per client IP)
"""

import pytest
from flask import Flask, request
from limits.storage import storage_from_string
from limits.strategies import STRATEGIES

import app.login.login_routes as login_routes
from app.utils.rate_limit import apply_proxy_fix, limiter, login_username_key


WRONG_PASSWORD = "WrongPassword123!"


class FakeClock:
    """Replaces the clock used by the in-memory rate-limit storage only."""

    def __init__(self):
        import time

        self.now = time.time()

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture()
def fake_clock(monkeypatch):
    import limits.storage.memory as memory_storage

    clock = FakeClock()
    monkeypatch.setattr(memory_storage, "time", clock)
    return clock


@pytest.fixture()
def password_check_spy(monkeypatch):
    """Counts password-hash checks done by the login view for unknown users."""
    calls = []
    real_check = login_routes.check_password_hash

    def spy(pwhash, password):
        calls.append(pwhash)
        return real_check(pwhash, password)

    monkeypatch.setattr(login_routes, "check_password_hash", spy)
    return calls


def _login(client, name, password, **kwargs):
    return client.post("/login", json={"name": name, "password": password}, **kwargs)


# ============================================================
# Per-IP login limit
# ============================================================


def test_eleventh_login_from_one_ip_is_rejected_before_password_check(
    client, rate_limited, password_check_spy
):
    # Different unknown usernames, so only the per-IP limit can trigger.
    for attempt in range(10):
        response = _login(client, f"nobody{attempt}", WRONG_PASSWORD)
        assert response.status_code == 401

    assert len(password_check_spy) == 10

    response = _login(client, "nobody-final", WRONG_PASSWORD)

    assert response.status_code == 429
    data = response.get_json()
    assert data["error"].startswith("Too many login attempts from this network.")
    assert "Please try again in" in data["error"]
    assert 1 <= data["retry_after"] <= 60
    assert int(response.headers["Retry-After"]) >= 1

    # The rejected request never reached the (expensive) password hash.
    assert len(password_check_spy) == 10


def test_each_client_ip_has_its_own_bucket(client, rate_limited):
    for attempt in range(10):
        _login(
            client,
            f"nobody{attempt}",
            WRONG_PASSWORD,
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        )

    blocked = _login(
        client, "nobody", WRONG_PASSWORD, environ_base={"REMOTE_ADDR": "10.0.0.1"}
    )
    other_ip = _login(
        client, "nobody", WRONG_PASSWORD, environ_base={"REMOTE_ADDR": "10.0.0.2"}
    )

    assert blocked.status_code == 429
    assert other_ip.status_code == 401


def test_spoofed_forwarded_for_header_does_not_bypass_the_ip_limit(
    client, rate_limited
):
    # TRUSTED_PROXY_COUNT is 0 in tests: X-Forwarded-For must be ignored.
    for attempt in range(10):
        _login(
            client,
            f"nobody{attempt}",
            WRONG_PASSWORD,
            headers={"X-Forwarded-For": f"198.51.100.{attempt}"},
        )

    response = _login(
        client,
        "nobody",
        WRONG_PASSWORD,
        headers={"X-Forwarded-For": "198.51.100.200"},
    )

    assert response.status_code == 429


# ============================================================
# Per-account failed-login limit
# ============================================================


def test_five_failed_logins_lock_the_account_even_with_the_right_password(
    client, rate_limited, test_user, other_user
):
    for _ in range(5):
        assert _login(client, "testuser", WRONG_PASSWORD).status_code == 401

    response = _login(client, "testuser", "TestPassword123!")

    assert response.status_code == 429
    assert response.get_json()["error"].startswith(
        "Too many failed login attempts for this account."
    )

    # Other accounts are unaffected.
    assert _login(client, "otheruser", "OtherPassword123!").status_code == 200


def test_successful_logins_do_not_use_up_the_failure_allowance(
    client, rate_limited, test_user
):
    for _ in range(3):
        assert _login(client, "testuser", "TestPassword123!").status_code == 200

    # Five failures are still allowed after three successes...
    for _ in range(5):
        assert _login(client, "testuser", WRONG_PASSWORD).status_code == 401

    # ...and only the sixth attempt is blocked (9 requests: under the IP limit).
    assert _login(client, "testuser", WRONG_PASSWORD).status_code == 429


def test_login_works_again_after_the_window_passes(
    client, rate_limited, test_user, fake_clock
):
    for _ in range(5):
        _login(client, "testuser", WRONG_PASSWORD)

    assert _login(client, "testuser", "TestPassword123!").status_code == 429

    fake_clock.advance(15 * 60 + 1)

    assert _login(client, "testuser", "TestPassword123!").status_code == 200


def test_account_key_is_a_fixed_length_hash_not_the_username(app):
    def key_for(name):
        with app.test_request_context("/login", method="POST", json={"name": name}):
            return login_username_key()

    key = key_for("testuser")

    assert key == key_for("testuser")
    assert key != key_for("otheruser")
    assert "testuser" not in key
    assert len(key) == len("user:") + 32
    assert len(key_for("x" * 10_000)) == len(key)


# ============================================================
# Register limit
# ============================================================


def test_fourth_registration_attempt_per_hour_is_rejected(client, rate_limited):
    # Invalid payloads still count, so no database rows are created here.
    for _ in range(3):
        assert client.post("/register", json={}).status_code == 400

    response = client.post("/register", json={})

    assert response.status_code == 429
    assert response.get_json()["error"].startswith(
        "Too many registration attempts from this network."
    )


# ============================================================
# Response format and resilience
# ============================================================


def test_429_response_carries_cors_headers_so_the_frontend_can_read_it(
    app, client, rate_limited
):
    origin = str(app.config["CORS_ORIGINS"]).split(",")[0].strip()

    for attempt in range(10):
        _login(client, f"nobody{attempt}", WRONG_PASSWORD)

    response = _login(client, "nobody", WRONG_PASSWORD, headers={"Origin": origin})

    assert response.status_code == 429
    assert response.headers.get("Access-Control-Allow-Origin") == origin


def test_rate_limits_still_apply_when_redis_is_unreachable(
    client, rate_limited, test_user, monkeypatch
):
    # Point the limiter at a Redis that does not exist (nothing listens on
    # port 1). Flask-Limiter must fall back to in-memory counters instead of
    # failing open or turning requests into 500s.
    dead_storage = storage_from_string(
        "redis://127.0.0.1:1/0",
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )
    monkeypatch.setattr(limiter, "_storage", dead_storage)
    monkeypatch.setattr(limiter, "_limiter", STRATEGIES["moving-window"](dead_storage))
    monkeypatch.setattr(limiter, "_storage_dead", False)

    assert _login(client, "testuser", "TestPassword123!").status_code == 200
    assert limiter._storage_dead is True

    for _ in range(5):
        assert _login(client, "testuser", WRONG_PASSWORD).status_code == 401

    assert _login(client, "testuser", "TestPassword123!").status_code == 429


# ============================================================
# Login hardening that ships with the limiter
# ============================================================


def test_unknown_username_still_runs_a_password_hash(
    client, rate_limited, password_check_spy
):
    response = _login(client, "does-not-exist", WRONG_PASSWORD)

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid credentials"
    # One dummy hash check, so the response takes as long as a wrong password.
    assert len(password_check_spy) == 1
    assert password_check_spy[0].startswith("pbkdf2:sha256:")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"data": "not json", "content_type": "text/plain"},
        {"json": {"name": 123, "password": "x"}},
        {"json": {"name": "testuser", "password": ["x"]}},
        {"json": ["not", "an", "object"]},
    ],
)
def test_malformed_login_bodies_return_400_not_500(client, kwargs):
    response = client.post("/login", **kwargs)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Name and password required"


def test_register_without_json_body_returns_400_not_500(client):
    response = client.post("/register", data="x", content_type="text/plain")

    assert response.status_code == 400


# ============================================================
# ProxyFix configuration
# ============================================================


def _remote_addr_seen(trusted_proxy_count, forwarded_for):
    probe = Flask("proxy_probe")
    probe.config["TRUSTED_PROXY_COUNT"] = trusted_proxy_count
    apply_proxy_fix(probe)

    @probe.route("/ip")
    def ip():
        return request.remote_addr

    response = probe.test_client().get(
        "/ip",
        headers={"X-Forwarded-For": forwarded_for},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    return response.get_data(as_text=True)


def test_proxy_fix_trusts_only_the_proxy_appended_address():
    # Client sent a fake "6.6.6.6"; the trusted proxy appended the real IP.
    assert _remote_addr_seen(1, "6.6.6.6, 203.0.113.7") == "203.0.113.7"


def test_no_trusted_proxies_means_forwarded_headers_are_ignored():
    assert _remote_addr_seen(0, "6.6.6.6, 203.0.113.7") == "10.0.0.1"
