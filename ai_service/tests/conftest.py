"""Shared fixtures.

Integration tests use a separate database, `ppa_ai_test`, in the same local
container, so running tests never touches the real knowledge base in `ppa_ai`.
"""

import asyncio
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

from app.config import Settings
from app.migrate import apply_migrations

TEST_DB = "ppa_ai_test"


def _with_database(dsn: str, name: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit(parts._replace(path=f"/{name}"))


async def _prepare_test_database(admin_dsn: str, test_dsn: str) -> None:
    admin = await asyncpg.connect(admin_dsn, timeout=3)
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB):
            await admin.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await admin.close()
    conn = await asyncpg.connect(test_dsn, timeout=3)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Fresh schema for every test run.
        await conn.execute("DROP SCHEMA IF EXISTS ai CASCADE")
        await conn.execute("CREATE SCHEMA ai")
        await apply_migrations(conn)
    finally:
        await conn.close()


@pytest.fixture(scope="session")
def test_dsn() -> str:
    settings = Settings()
    if settings.database_url is None:
        pytest.skip("AI_DATABASE_URL is not set")
    admin_dsn = settings.database_url.get_secret_value()
    dsn = _with_database(admin_dsn, TEST_DB)
    try:
        asyncio.run(_prepare_test_database(admin_dsn, dsn))
    except (OSError, asyncio.TimeoutError, asyncpg.PostgresError) as exc:
        pytest.skip(f"local pgvector database is not available ({type(exc).__name__})")
    return dsn


@pytest.fixture
async def pool(test_dsn):
    pool = await asyncpg.create_pool(test_dsn, min_size=1, max_size=4)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE ai.documents, ai.chunks RESTART IDENTITY CASCADE")
    yield pool
    await pool.close()
