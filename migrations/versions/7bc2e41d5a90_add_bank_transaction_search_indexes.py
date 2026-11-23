"""add trigram indexes for bank transaction text search

Revision ID: 7bc2e41d5a90
Revises: 5e8be4a72fc9
Create Date: 2026-10-23

These partial GIN indexes support case-insensitive substring searching for
bank transaction descriptions and categories without indexing rows belonging
to the other transaction subclasses.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7bc2e41d5a90"
down_revision = "5e8be4a72fc9"
branch_labels = None
depends_on = None


def upgrade():
    # pg_trgm supplies gin_trgm_ops, which supports LIKE/ILIKE substring
    # searches. Keep the extension on downgrade because it may be shared by
    # other application features or already have existed before this migration.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    bind = op.get_bind()
    trigram_schema = bind.execute(
        sa.text(
            """
            SELECT n.nspname
            FROM pg_extension e
            JOIN pg_namespace n ON n.oid = e.extnamespace
            WHERE e.extname = 'pg_trgm'
            """
        )
    ).scalar_one()
    quoted_schema = bind.dialect.identifier_preparer.quote_schema(trigram_schema)

    op.execute(
        f'''CREATE INDEX ix_transaction_bank_description_trgm
            ON "transaction" USING gin (description {quoted_schema}.gin_trgm_ops)
            WHERE type = 'bank_transaction' '''
    )
    op.execute(
        f'''CREATE INDEX ix_transaction_bank_category_trgm
            ON "transaction" USING gin (category {quoted_schema}.gin_trgm_ops)
            WHERE type = 'bank_transaction' '''
    )


def downgrade():
    op.drop_index("ix_transaction_bank_category_trgm", table_name="transaction")
    op.drop_index("ix_transaction_bank_description_trgm", table_name="transaction")
