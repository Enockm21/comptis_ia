"""Add org_integrations table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "org_integrations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("api_url", sa.String(500), nullable=True),
        sa.Column("mcp_url", sa.String(500), nullable=True),
        sa.Column("token_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_org_integration_org_name"),
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON org_integrations TO comptis_app")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON org_integrations FROM comptis_app")
    op.drop_table("org_integrations")
