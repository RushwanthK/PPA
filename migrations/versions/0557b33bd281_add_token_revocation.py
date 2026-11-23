"""add token revocation (user.token_version, revoked_token)

Revision ID: 0557b33bd281
Revises: 7bc2e41d5a90
Create Date: 2026-11-22

* user.token_version: copied into each access token as the "ver" claim;
  incrementing it invalidates every token issued before (password change,
  "log out of all devices"). Existing rows get 0, which matches tokens issued
  before this migration (they have no "ver" claim and are treated as 0), so
  nobody is logged out by deploying it.
* revoked_token: single-token logout list, pruned by expires_at.

Both changes are additive. Adding a NOT NULL column with a constant default
is a metadata-only change on PostgreSQL 11+, so it does not rewrite the table.
The old application code keeps working against the upgraded schema, so this
migration can (and must) be applied before the new backend is deployed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0557b33bd281"
down_revision = "7bc2e41d5a90"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "revoked_token",
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index(
        "ix_revoked_token_expires_at",
        "revoked_token",
        ["expires_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_revoked_token_expires_at", table_name="revoked_token")
    op.drop_table("revoked_token")
    op.drop_column("user", "token_version")
