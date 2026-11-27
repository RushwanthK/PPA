import asyncio

import pytest
from fastapi.testclient import TestClient

from app import db as db_module
from app.config import Settings
from app.db import Database, DatabaseUnavailable
from app.main import create_app, get_db


def make_settings(**overrides) -> Settings:
    # _env_file=None: tests never read the developer's real ai_service/.env
    values = {"AI_ENV": "test", "AI_DATABASE_URL": None, **overrides}
    return Settings(_env_file=None, **values)


class FakeDatabase:
    def __init__(self, version=None, error=False):
        self.version = version
        self.error = error

    async def vector_version(self):
        if self.error:
            raise DatabaseUnavailable()
        return self.version


def client_with(fake: FakeDatabase, **settings) -> TestClient:
    app = create_app(make_settings(**settings))
    app.dependency_overrides[get_db] = lambda: fake
    return TestClient(app)


# ---- Liveness ----------------------------------------------------------------

def test_live_is_ok_without_a_database():
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---- Readiness ---------------------------------------------------------------

def test_ready_when_database_and_pgvector_are_available():
    with client_with(FakeDatabase(version="0.8.1")) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "ok", "vector_extension": "0.8.1"},
    }


def test_not_ready_when_database_is_unavailable():
    with client_with(FakeDatabase(error=True)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable", "vector_extension": None},
    }


def test_not_ready_when_pgvector_is_missing():
    with client_with(FakeDatabase(version=None)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "vector_extension": "missing"}


def test_ready_without_database_url_reports_unavailable():
    # Real Database object, no URL configured: the service still starts.
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"


# ---- Configuration and exposure ---------------------------------------------

def test_api_docs_available_outside_production():
    with TestClient(create_app(make_settings(AI_ENV="development"))) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_api_docs_disabled_in_production():
    with TestClient(create_app(make_settings(AI_ENV="production"))) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/redoc").status_code == 404


def test_database_password_never_appears_in_settings_repr():
    settings = make_settings(AI_DATABASE_URL="postgresql://u:super-secret-pw@localhost:5434/db")
    assert "super-secret-pw" not in repr(settings)
    assert "super-secret-pw" not in str(settings.model_dump())
    assert "super-secret-pw" in settings.database_url.get_secret_value()


def test_invalid_environment_name_is_rejected():
    with pytest.raises(ValueError):
        make_settings(AI_ENV="prod")


# ---- Database class (async) --------------------------------------------------

async def test_connect_without_dsn_returns_false_and_query_raises():
    database = Database(None)
    assert await database.connect() is False
    with pytest.raises(DatabaseUnavailable):
        await database.vector_version()


async def test_connect_to_unreachable_database_fails_fast(caplog):
    # Port 1 on localhost refuses immediately; the password must not be logged.
    database = Database("postgresql://u:leak-check-pw@127.0.0.1:1/db", timeout=2.0)
    assert await asyncio.wait_for(database.connect(), timeout=5) is False
    assert "leak-check-pw" not in caplog.text


async def test_concurrent_connects_create_only_one_pool(monkeypatch):
    calls = 0

    class FakePool:
        async def close(self):
            pass

    async def fake_create_pool(*args, **kwargs):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)  # give the other tasks a chance to race
        return FakePool()

    monkeypatch.setattr(db_module.asyncpg, "create_pool", fake_create_pool)
    database = Database("postgresql://u:p@localhost/db")
    results = await asyncio.gather(*(database.connect() for _ in range(10)))
    assert all(results)
    assert calls == 1
    await database.close()
    assert database.connected is False
