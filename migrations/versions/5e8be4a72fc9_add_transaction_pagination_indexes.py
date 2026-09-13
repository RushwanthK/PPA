"""add transaction pagination indexes

Revision ID: 5e8be4a72fc9
Revises: 8489c496e290
Create Date: 2026-09-09 17:47:05.791085

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e8be4a72fc9'
down_revision = '8489c496e290'
branch_labels = None
depends_on = None


def upgrade():
    # Bank transaction history
    op.create_index(
        "ix_transaction_bank_date_id",
        "transaction",
        ["bank_id", "date", "id"],
        unique=False,
    )

    # Credit card transaction history
    op.create_index(
        "ix_transaction_credit_card_date_id",
        "transaction",
        ["credit_card_id", "date", "id"],
        unique=False,
    )

    # Asset transaction history
    op.create_index(
        "ix_transaction_asset_date_id",
        "transaction",
        ["asset_id", "date", "id"],
        unique=False,
    )

    # Savings transaction history
    op.create_index(
        "ix_transaction_saving_date_id",
        "transaction",
        ["saving_id", "date", "id"],
        unique=False,
    )

    # Transfer history
    op.create_index(
        "ix_transfer_transaction_user_date_id",
        "transfer_transaction",
        ["user_id", "date", "id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_transfer_transaction_user_date_id",
        table_name="transfer_transaction",
    )

    op.drop_index(
        "ix_transaction_saving_date_id",
        table_name="transaction",
    )

    op.drop_index(
        "ix_transaction_asset_date_id",
        table_name="transaction",
    )

    op.drop_index(
        "ix_transaction_credit_card_date_id",
        table_name="transaction",
    )

    op.drop_index(
        "ix_transaction_bank_date_id",
        table_name="transaction",
    )