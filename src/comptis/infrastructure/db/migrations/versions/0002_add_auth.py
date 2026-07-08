"""Add password_hash to users and create api_keys table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=False, server_default=""),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON api_keys TO comptis_app")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON api_keys FROM comptis_app")
    op.drop_table("api_keys")
    op.drop_column("users", "password_hash")
