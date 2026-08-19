from sqlalchemy import text

from app import db


def test_database_connection(app):
    with app.app_context():
        result = db.session.execute(text("SELECT 1"))

        assert result.scalar() == 1

def test_database_tables_created(app):
    from sqlalchemy import inspect

    with app.app_context():
        inspector = inspect(db.engine)

        tables = set(inspector.get_table_names())

        assert "user" in tables
        assert "bank" in tables
        assert "credit_card" in tables
        assert "asset" in tables
        assert "saving" in tables
        assert "transaction" in tables
        assert "transfer_transaction" in tables