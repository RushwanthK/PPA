"""Runs against the real local pgvector container. Skipped when it is not running.

    docker compose -f ai_service/docker-compose.yml up -d
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Database
from app.main import create_app

pytestmark = pytest.mark.integration


def _unavailable(reason: str):
    # In CI (CI=true) the database must be there: fail rather than skip (see conftest.py).
    if os.environ.get("CI", "").lower() == "true":
        pytest.fail(f"{reason} (CI)")
    pytest.skip(reason)


@pytest.fixture
def settings():
    s = Settings()  # reads ai_service/.env
    if s.database_url is None:
        _unavailable("AI_DATABASE_URL is not set")
    return s


@pytest.fixture
async def database(settings):
    db = Database(settings.database_url.get_secret_value(), timeout=3.0)
    if not await db.connect():
        _unavailable("local pgvector database is not running")
    yield db
    await db.close()


async def test_pgvector_extension_is_installed(database):
    version = await database.vector_version()
    assert version is not None and version.startswith("0.8")


async def test_ai_schema_exists(database):
    async with database._pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT 1 FROM pg_namespace WHERE nspname = 'ai'"
        ) == 1


async def test_vector_similarity_works(database):
    # The core operation RAG relies on: order rows by distance to a query vector.
    async with database._pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT name FROM (VALUES
                ('close', '[1, 0, 0]'::vector),
                ('far',   '[0, 1, 0]'::vector)
            ) AS t(name, embedding)
            ORDER BY embedding <=> '[0.9, 0.1, 0]'::vector
            """
        )
    assert [r["name"] for r in rows] == ["close", "far"]


def test_ready_endpoint_against_real_database(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"
