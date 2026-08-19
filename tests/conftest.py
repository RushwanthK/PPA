import os

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

# Load test environment BEFORE importing the Flask application.
load_dotenv(".env.test", override=True)

# These imports must happen after the test environment is loaded.
from app import create_app, db


TEST_DATABASE_URL = os.environ.get("DATABASE_URL")


def _validate_test_database():
    """Prevent pytest from accidentally using a non-test database."""

    if not TEST_DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not configured for testing. "
            "Check .env.test."
        )

    database_name = make_url(TEST_DATABASE_URL).database

    if database_name != "ppa_test":
        raise RuntimeError(
            f"Unsafe test database: '{database_name}'. "
            "Pytest must use the 'ppa_test' database."
        )


_validate_test_database()


import pytest


@pytest.fixture(scope="session")
def app():
    """Create one Flask application for the test session."""

    app = create_app()

    app.config.update(
        TESTING=True
    )

    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Create a Flask test client."""

    return app.test_client()