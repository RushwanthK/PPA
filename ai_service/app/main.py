"""PPA AI service: FastAPI application factory.

Run locally from the ai_service folder:
    .venv\\Scripts\\python -m uvicorn app.main:create_app --factory --port 8001 --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import httpx

from .assistant.auth import FlaskAuthClient
from .assistant.factory import build_assistant
from .assistant.routes import ApiError, api_error_handler
from .assistant.routes import router as assistant_router
from .config import Settings, get_settings
from .db import Database, DatabaseUnavailable
from .logging_setup import configure_logging
from .request_context import RequestContextMiddleware

log = logging.getLogger("ppa_ai")

VERSION = "0.1.0"


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyChecks(BaseModel):
    database: Literal["ok", "unavailable"]
    vector_extension: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadyChecks


def get_db(request: Request) -> Database:
    """Dependency: the shared Database. Tests replace it via app.dependency_overrides."""
    return request.app.state.db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: try to open the pool, but do not crash if the database is down.
        # /health/ready reports it, and the pool is created on a later request.
        db = Database(
            settings.database_url.get_secret_value() if settings.database_url else None,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            timeout=settings.db_timeout_seconds,
        )
        await db.connect()
        app.state.db = db
        # One shared HTTP client (connection pooling) for Flask, Groq and Gemini calls.
        http = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
        app.state.http = http
        app.state.auth_client = FlaskAuthClient(settings.flask_api_url, http,
                                                cache_seconds=settings.auth_cache_seconds)
        app.state.assistant = await build_assistant(settings, db, http) if settings.ai_enabled else None
        log.info("PPA AI service started (env=%s, database=%s, assistant=%s)",
                 settings.env, "connected" if db.connected else "unavailable",
                 "ready" if app.state.assistant else "off")
        yield
        # Shutdown: close connections cleanly.
        await http.aclose()
        await db.close()

    app = FastAPI(
        title="PPA AI Service",
        version=VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.state.settings = settings
    app.state.assistant = None
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(RequestContextMiddleware)
    # CORS: only listed origins, only the methods and headers the chat panel uses, and no
    # cookies (auth is the Authorization header, like the Flask API). Added last, so it is
    # the outermost layer and also answers preflight requests.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Retry-After", "X-Request-ID"],
        allow_credentials=False,
        max_age=600,
    )
    app.include_router(assistant_router)

    @app.get("/health/live", response_model=LiveResponse, tags=["health"])
    async def live() -> LiveResponse:
        """Liveness: the process is up. Never touches the database, so a slow or
        sleeping database does not make the platform restart a healthy process."""
        return LiveResponse(status="ok")

    @app.get(
        "/health/ready",
        response_model=ReadyResponse,
        responses={503: {"model": ReadyResponse}},
        tags=["health"],
    )
    async def ready(db: Database = Depends(get_db)):
        """Readiness: the service can do real work (database reachable, pgvector installed)."""
        try:
            version = await db.vector_version()
        except DatabaseUnavailable:
            body = ReadyResponse(status="not_ready", checks=ReadyChecks(database="unavailable"))
            return JSONResponse(status_code=503, content=body.model_dump())
        if version is None:
            body = ReadyResponse(
                status="not_ready", checks=ReadyChecks(database="ok", vector_extension="missing")
            )
            return JSONResponse(status_code=503, content=body.model_dump())
        return ReadyResponse(status="ready", checks=ReadyChecks(database="ok", vector_extension=version))

    return app
