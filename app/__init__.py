import logging
from time import perf_counter
from uuid import uuid4

from flask import Flask, current_app, g, has_request_context, request
from sqlalchemy import event
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager


load_dotenv()

db = SQLAlchemy()
migrate = Migrate()


def _performance_request_active():
    """Return True only during a request with opt-in timing enabled."""
    return (
        has_request_context()
        and current_app.config.get("PERF_DIAGNOSTICS_ENABLED", False)
        and hasattr(g, "_ppa_perf_request_started_at")
    )


def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Start timing a DBAPI cursor execution without recording SQL or parameters."""
    if not _performance_request_active():
        return

    conn.info.setdefault("_ppa_perf_sql_start_times", []).append(perf_counter())

    if getattr(g, "_ppa_perf_first_sql_start_ms", None) is None:
        g._ppa_perf_first_sql_start_ms = (
            perf_counter() - g._ppa_perf_request_started_at
        ) * 1000

    g._ppa_perf_sql_count += 1


def _record_cursor_execution_time(conn):
    """Accumulate cursor.execute time; result fetching is not fully included."""
    if conn is None:
        return

    start_times = conn.info.get("_ppa_perf_sql_start_times")
    if not start_times:
        return

    started_at = start_times.pop()
    if not start_times:
        conn.info.pop("_ppa_perf_sql_start_times", None)

    if not _performance_request_active():
        return

    g._ppa_perf_sql_execution_ms += (perf_counter() - started_at) * 1000


def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    _record_cursor_execution_time(conn)


def _handle_sql_error(exception_context):
    _record_cursor_execution_time(exception_context.connection)


def create_app():
    app = Flask(__name__)

    from config import get_config

    app.config.from_object(get_config())

    if app.config.get("PERF_DIAGNOSTICS_ENABLED", False):
        app.logger.setLevel(logging.INFO)

    jwt = JWTManager(app)

    # HS256 tokens are only as strong as this key: anyone holding one token
    # can try to guess a short key offline and then forge tokens for any
    # user. RFC 7518 requires at least 32 bytes. Warn loudly (Render logs)
    # rather than refuse to start, so a weak key cannot take the site down.
    if len(str(app.config["JWT_SECRET_KEY"]).encode()) < 32:
        app.logger.warning(
            "JWT_SECRET_KEY is shorter than 32 bytes; set a long random value "
            "(e.g. python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
        )

    # Token revocation checks and uniform 401 replies (see utils/auth_tokens.py).
    from .utils.auth_tokens import register_jwt_callbacks

    register_jwt_callbacks(jwt)

    # ProxyFix + Flask-Limiter. Must run before the blueprints are used so the
    # limiter's before_request hook rejects excess requests before any view
    # (and its password hashing) runs.
    from .utils.rate_limit import init_rate_limiting

    init_rate_limiting(app)

    # JSON 413 for oversized bodies and a generic JSON 500 (no internals).
    from .utils.errors import register_error_handlers

    register_error_handlers(app)

    db.init_app(app)
    migrate.init_app(app, db)

    # Redis is optional. Without REDIS_URL the application keeps its existing
    # database-backed behavior. The client connects lazily on the first command.
    app.extensions["ppa_dashboard_redis"] = None
    redis_url = app.config.get("REDIS_URL")
    if redis_url:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "REDIS_URL is configured, but the redis package is not installed"
            ) from exc

        app.extensions["ppa_dashboard_redis"] = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            health_check_interval=30,
            max_connections=app.config["REDIS_MAX_CONNECTIONS"],
        )

    # Allow local development and tests to use the same local CORS behavior.
    CORS(
        app,
        resources={
            r"/*": {
                "origins": app.config["CORS_ORIGINS"]
            }
        },
        # Auth uses the Authorization header, not cookies, so browsers are
        # not asked to send credentials cross-origin (no
        # Access-Control-Allow-Credentials). The frontend's axios client
        # matches this (no withCredentials).
        supports_credentials=False,
        allow_headers=["Content-Type", "Authorization"],
        max_age=600,
    )

    from .routes import routes
    from .dashboard.dashboard_routes import dashboard_routes
    from .users.users_routes import users_routes
    from .banks.bank_routes import bank_routes
    from .savings.savings_routes import savings_routes
    from .assets.assets_routes import assets_routes
    from .credit_cards.credit_card_routes import credit_card_routes
    from .login.login_routes import login_routes


    app.register_blueprint(routes)
    app.register_blueprint(dashboard_routes)
    app.register_blueprint(users_routes)
    app.register_blueprint(bank_routes)
    app.register_blueprint(savings_routes)
    app.register_blueprint(assets_routes)
    app.register_blueprint(credit_card_routes)
    app.register_blueprint(login_routes)

    @app.before_request
    def start_performance_measurement():
        if not app.config.get("PERF_DIAGNOSTICS_ENABLED", False):
            return

        g._ppa_perf_request_started_at = perf_counter()
        g._ppa_perf_request_id = uuid4().hex
        g._ppa_perf_sql_count = 0
        g._ppa_perf_sql_execution_ms = 0.0
        g._ppa_perf_first_sql_start_ms = None

    @app.after_request
    def add_headers(response):
        if response.content_type:
            if response.content_type.startswith("text/html"):
                response.headers["Content-Type"] = "text/html; charset=utf-8"

            elif response.content_type.startswith("application/json"):
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

        response.headers["X-Content-Type-Options"] = "nosniff"

        # This is a JSON/file API: it never needs to be framed, load scripts
        # or styles, or leak its URL in a Referer header.
        response.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # Browsers ignore HSTS on plain-HTTP responses (local development),
        # so it only takes effect on Render's HTTPS URL.
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000"
        )

        if (
            app.config.get("PERF_DIAGNOSTICS_ENABLED", False)
            and hasattr(g, "_ppa_perf_request_started_at")
        ):
            request_id = g._ppa_perf_request_id
            app_ms = (perf_counter() - g._ppa_perf_request_started_at) * 1000
            response.headers["X-Request-ID"] = request_id

            # Do not log query strings, request bodies, SQL text, SQL parameters,
            # user identifiers, or financial values.
            app.logger.info(
                "ppa_perf request_id=%s method=%s endpoint=%s status=%s "
                "app_ms=%.2f first_sql_start_ms=%s sql_count=%d "
                "sql_execute_ms=%.2f",
                request_id,
                request.method,
                request.endpoint or "unmatched",
                response.status_code,
                app_ms,
                (
                    "n/a"
                    if g._ppa_perf_first_sql_start_ms is None
                    else f"{g._ppa_perf_first_sql_start_ms:.2f}"
                ),
                g._ppa_perf_sql_count,
                g._ppa_perf_sql_execution_ms,
            )

        return response

    # Attach SQL timing hooks only when explicitly enabled. The hooks record
    # execution counts and cursor.execute durations, never SQL text or values.
    if app.config.get("PERF_DIAGNOSTICS_ENABLED", False):
        with app.app_context():
            engine = db.engine
            event.listen(engine, "before_cursor_execute", _before_cursor_execute)
            event.listen(engine, "after_cursor_execute", _after_cursor_execute)
            event.listen(engine, "handle_error", _handle_sql_error)

    return app
