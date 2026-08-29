import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from datetime import date

load_dotenv(".env.test", override=True)

from app import create_app, db
from app.models import User, Transaction


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


@pytest.fixture(scope="session")
def app():
    """Create one Flask application for the complete test session."""

    app = create_app()

    assert app.config["TESTING"] is True

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


@pytest.fixture()
def db_session(app):
    """Provide a database session for individual tests."""

    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture()
def database_tables(app):
    """Return the test database table names."""

    with app.app_context():
        inspector = inspect(db.engine)
        return set(inspector.get_table_names())


@pytest.fixture()
def test_user(db_session):
    user = User(
        name="testuser",
        age=30,
        dob=date(1996, 1, 1),
        place="Bengaluru",
    )

    user.set_password("TestPassword123!")

    db_session.add(user)
    db_session.commit()

    yield user

    db_session.rollback()

    # Remove transactions created by the test before deleting the user.
    db_session.query(Transaction).filter(
        Transaction.user_id == user.id
    ).delete(synchronize_session=False)

    db_session.commit()

    existing_user = db_session.get(User, user.id)

    if existing_user is not None:
        db_session.delete(existing_user)
        db_session.commit()


@pytest.fixture()
def authenticated_client(client, test_user):
    response = client.post(
        "/login",
        json={
            "name": "testuser",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    token = response.get_json()["token"]

    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    return client


@pytest.fixture()
def other_user(db_session):
    user = User(
        name="otheruser",
        age=28,
        dob=date(1997, 3, 15),
        place="Mysuru",
    )

    user.set_password("OtherPassword123!")

    db_session.add(user)
    db_session.commit()

    yield user

    db_session.rollback()

    db_session.query(Transaction).filter(
        Transaction.user_id == user.id
    ).delete(synchronize_session=False)

    db_session.commit()

    existing_user = db_session.get(User, user.id)

    if existing_user is not None:
        db_session.delete(existing_user)
        db_session.commit()


@pytest.fixture()
def test_bank(db_session, test_user):
    from app.models import Bank, BankTransaction

    bank = Bank(
        name="Test Bank",
        balance=10000,
        user_id=test_user.id,
    )

    db_session.add(bank)
    db_session.commit()

    yield bank

    db_session.rollback()

    # Delete transactions belonging to this bank first.
    db_session.query(BankTransaction).filter(
        BankTransaction.bank_id == bank.id
    ).delete(synchronize_session=False)

    db_session.commit()

    existing_bank = db_session.get(Bank, bank.id)

    if existing_bank is not None:
        db_session.delete(existing_bank)
        db_session.commit()