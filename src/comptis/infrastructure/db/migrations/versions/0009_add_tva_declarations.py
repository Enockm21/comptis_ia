"""add tva_declarations table

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tva_declarations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=False),
        sa.Column("tva_collectee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tva_deductible", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("tva_nette", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("lignes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deposee_le", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payee_le", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute("""
        ALTER TABLE tva_declarations ENABLE ROW LEVEL SECURITY;

        CREATE POLICY tva_declarations_tenant_isolation ON tva_declarations
            USING (
                tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
            );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tva_declarations_tenant_isolation ON tva_declarations;")
    op.drop_table("tva_declarations")
