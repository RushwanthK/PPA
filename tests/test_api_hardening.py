"""Security regression tests for API-wide hardening.

* every route requires a JWT unless it is explicitly public;
* oversized request bodies are refused with a JSON 413;
* 500 replies never contain exception text;
* CORS does not advertise credentials; security headers are present.
"""

import re

import pytest

from app import db
from app.utils.errors import GENERIC_SERVER_ERROR


# Routes that must work without a token. Adding a route here is a deliberate
# security decision; any other new route without @jwt_required fails below.
PUBLIC_ENDPOINTS = {
    "routes.home",
    "login_routes.login",
    "login_routes.register",
    "static",
}


def _sample_url(rule):
    # Replace every URL parameter (<int:id>, <path:filename>, ...) with a value.
    return re.sub(r"<(?:[^:>]+:)?[^>]+>", "999999", rule.rule)


def test_every_non_public_route_requires_a_token(app, client):
    unprotected = []

    for rule in app.url_map.iter_rules():
        if rule.endpoint in PUBLIC_ENDPOINTS:
            continue

        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            response = client.open(
                _sample_url(rule),
                method=method,
                json={} if method in {"POST", "PUT", "PATCH"} else None,
            )
            if response.status_code != 401:
                unprotected.append(f"{method} {rule.rule} -> {response.status_code}")

    assert unprotected == []


def test_public_endpoints_list_has_no_stale_entries(app):
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}

    assert PUBLIC_ENDPOINTS <= endpoints


# ============================================================
# Request size limit
# ============================================================


def _oversized_json(app):
    limit = app.config["MAX_CONTENT_LENGTH"]
    return '{"name": "' + "x" * limit + '", "password": "x"}'


def test_oversized_login_body_is_refused_with_json_413(app, client):
    response = client.post(
        "/login", data=_oversized_json(app), content_type="application/json"
    )

    assert response.status_code == 413
    assert response.get_json()["error"].startswith("Request is too large")


def test_oversized_body_is_refused_on_authenticated_routes(app, authenticated_client):
    response = authenticated_client.post(
        "/banks", data=_oversized_json(app), content_type="application/json"
    )

    assert response.status_code == 413


def test_normal_sized_bodies_are_unaffected(client, test_user):
    response = client.post(
        "/login", json={"name": "testuser", "password": "TestPassword123!"}
    )

    assert response.status_code == 200


# ============================================================
# No exception details in error replies
# ============================================================


def test_handled_server_error_hides_exception_text_but_logs_it(
    authenticated_client, test_user, monkeypatch, caplog
):
    def failing_commit():
        raise RuntimeError("SECRET-DETAIL: relation \"user\" constraint xyz")

    monkeypatch.setattr(db.session, "commit", failing_commit)

    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={"name": "testuser", "dob": "1996-01-01", "place": "Mysuru"},
    )

    assert response.status_code == 500
    assert response.get_json() == {"error": GENERIC_SERVER_ERROR}
    assert "SECRET-DETAIL" not in response.get_data(as_text=True)
    # Still debuggable: the full exception is in the server log.
    assert "SECRET-DETAIL" in caplog.text


def test_unhandled_exception_returns_generic_json_500(app, client, monkeypatch):
    def broken_view():
        raise RuntimeError("SECRET-DETAIL from an unhandled error")

    # TESTING re-raises exceptions by default; production does not.
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    monkeypatch.setitem(app.view_functions, "routes.home", broken_view)

    response = client.get("/")

    assert response.status_code == 500
    assert response.get_json() == {"error": GENERIC_SERVER_ERROR}
    assert "SECRET-DETAIL" not in response.get_data(as_text=True)


# ============================================================
# CORS and security headers
# ============================================================


def _allowed_origin(app):
    return str(app.config["CORS_ORIGINS"]).split(",")[0].strip()


def test_cors_allows_the_frontend_origin_without_credentials(app, client):
    origin = _allowed_origin(app)

    preflight = client.options(
        "/banks",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert preflight.headers.get("Access-Control-Allow-Origin") == origin
    assert "authorization" in preflight.headers.get(
        "Access-Control-Allow-Headers", ""
    ).lower()
    assert "Access-Control-Allow-Credentials" not in preflight.headers


def test_cors_ignores_other_origins(client):
    response = client.get("/", headers={"Origin": "https://evil.example"})

    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.parametrize(
    "header, value",
    [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
        ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
        ("Strict-Transport-Security", "max-age=31536000"),
    ],
)
def test_security_headers_are_set(client, header, value):
    response = client.get("/")

    assert response.headers.get(header) == value


def test_security_headers_are_set_on_error_responses(client):
    response = client.get("/me")

    assert response.status_code == 401
    assert response.headers.get("X-Frame-Options") == "DENY"
