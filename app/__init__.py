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

    JWTManager(app)

    db.init_app(app)
    migrate.init_app(app, db)

    # Allow local development and tests to use the same local CORS behavior.
    CORS(
        app,
        resources={
            r"/*": {
                "origins": app.config["CORS_ORIGINS"]
            }
        },
        supports_credentials=True,
        expose_headers=["Authorization"],
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
