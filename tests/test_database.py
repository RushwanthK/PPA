from sqlalchemy import text

from app import db


def test_database_connection(app):
    with app.app_context():
        result = db.session.execute(text("SELECT 1"))

        assert result.scalar() == 1


def test_database_tables_created(database_tables):
    expected_tables = {
        "user",
        "bank",
        "credit_card",
        "asset",
        "saving",
        "transaction",
        "transfer_transaction",
    }

    assert expected_tables.issubset(database_tables)


def test_testing_configuration(app):
    assert app.config["TESTING"] is True