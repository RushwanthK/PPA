import os

import pytest
from dotenv import load_dotenv
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from datetime import date,datetime

load_dotenv(".env.test", override=True)

from app import create_app, db
from app.models import (
    Asset,
    AssetTransaction,
    Bank,
    BankTransaction,
    CreditCard,
    CreditCardTransaction,
    Saving,
    SavingTransaction,
    Transaction,
    User,
)


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


@pytest.fixture()
def test_saving(db_session, test_user, test_bank):
    from app.models import Saving, SavingTransaction

    saving = Saving(
        name="Test Saving",
        user_id=test_user.id,
        bank_id=test_bank.id,
        balance=5000,
    )

    db_session.add(saving)
    db_session.commit()

    yield saving

    db_session.rollback()

    # Delete saving transactions first because the relationship
    # does not currently use delete cascade.
    db_session.query(SavingTransaction).filter(
        SavingTransaction.saving_id == saving.id
    ).delete(synchronize_session=False)

    db_session.commit()

    existing_saving = db_session.get(Saving, saving.id)

    if existing_saving is not None:
        db_session.delete(existing_saving)
        db_session.commit()

@pytest.fixture()
def test_asset(
    db_session,
    test_user,
):
    asset = Asset(
        name="Test Asset",
        user_id=test_user.id,
        platform="Test Platform",
        category="Mutual Funds",
        balance=10000,
    )

    db_session.add(asset)
    db_session.commit()

    yield asset

    db_session.rollback()

    db_session.query(
        AssetTransaction
    ).filter(
        AssetTransaction.asset_id == asset.id
    ).delete(
        synchronize_session=False
    )

    db_session.commit()

    existing_asset = db_session.get(
        Asset,
        asset.id,
    )

    if existing_asset is not None:
        db_session.delete(
            existing_asset
        )

        db_session.commit()

@pytest.fixture()
def test_credit_card(db_session, test_user):
    card = CreditCard(
        name="Test Credit Card",
        user_id=test_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )

    db_session.add(card)
    db_session.commit()

    yield card

    db_session.rollback()

    db_session.query(CreditCardTransaction).filter(
        CreditCardTransaction.credit_card_id == card.id
    ).delete(synchronize_session=False)

    db_session.commit()

    existing_card = db_session.get(CreditCard, card.id)

    if existing_card is not None:
        db_session.delete(existing_card)
        db_session.commit()

@pytest.fixture()
def export_test_data(
    db_session,
    test_user,
):
    """
    Create one controlled transaction for each
    supported export category.

    This fixture intentionally creates data directly
    through the models rather than through API routes.
    Export tests are responsible for testing export
    behavior, not account/transaction creation.
    """

    bank = Bank(
        name="Export Test Bank",
        user_id=test_user.id,
        balance=1000,
    )

    saving = Saving(
        name="Export Test Saving",
        user_id=test_user.id,
        bank_id=bank.id,
        balance=2000,
    )

    asset = Asset(
        name="Export Test Asset",
        user_id=test_user.id,
        platform="Export Test Platform",
        category="Other",
        balance=3000,
    )

    credit_card = CreditCard(
        name="Export Test Credit Card",
        user_id=test_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=1000,
        billed_unpaid=0,
        unbilled_spends=1000,
    )

    db_session.add_all([
        bank,
        saving,
        asset,
        credit_card,
    ])

    db_session.commit()

    bank_transaction = BankTransaction(
        bank_id=bank.id,
        user_id=test_user.id,
        amount=1000,
        date=datetime(
            2026,
            1,
            10,
            10,
            0,
            0,
        ),
        description="BANK_EXPORT_TEST",
        category="Income",
        transaction_type="income",
        bank_balance_after=2000,
    )

    saving_transaction = SavingTransaction(
        saving_id=saving.id,
        user_id=test_user.id,
        amount=500,
        date=datetime(
            2026,
            1,
            11,
            10,
            0,
            0,
        ),
        description="SAVING_EXPORT_TEST",
        category="Savings",
        transaction_type="deposit",
        saving_balance_after=2500,
    )

    asset_transaction = AssetTransaction(
        asset_id=asset.id,
        user_id=test_user.id,
        amount=750,
        date=datetime(
            2026,
            1,
            12,
            10,
            0,
            0,
        ),
        description="ASSET_EXPORT_TEST",
        category="Investment",
        transaction_type="deposit",
        asset_balance_after=3750,
    )

    credit_card_transaction = (
        CreditCardTransaction(
            credit_card_id=credit_card.id,
            user_id=test_user.id,
            amount=-250,
            date=datetime(
                2026,
                1,
                13,
                10,
                0,
                0,
            ),
            description="CARD_EXPORT_TEST",
            category="Shopping",
            transaction_type="expense",
            card_balance_after=1250,
            is_payment=False,
            is_billed=False,
        )
    )

    db_session.add_all([
        bank_transaction,
        saving_transaction,
        asset_transaction,
        credit_card_transaction,
    ])

    db_session.commit()

    yield {
        "bank": bank,
        "saving": saving,
        "asset": asset,
        "credit_card": credit_card,
        "bank_transaction": bank_transaction,
        "saving_transaction": saving_transaction,
        "asset_transaction": asset_transaction,
        "credit_card_transaction": (
            credit_card_transaction
        ),
    }

    db_session.rollback()

    db_session.query(
        Transaction
    ).filter(
        Transaction.user_id == test_user.id
    ).delete(
        synchronize_session=False
    )

    db_session.commit()

    for model, object_id in [
        (Saving, saving.id),
        (CreditCard, credit_card.id),
        (Asset, asset.id),
        (Bank, bank.id),
    ]:
        existing_object = db_session.get(
            model,
            object_id,
        )

        if existing_object is not None:
            db_session.delete(
                existing_object
            )

    db_session.commit()
