"""add grand_livre table for FEC double-entry accounting

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "grand_livre",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("journal_code", sa.String(10), nullable=False),
        sa.Column("journal_lib", sa.String(100), nullable=False),
        sa.Column("ecriture_num", sa.String(20), nullable=False),
        sa.Column("ecriture_date", sa.Date, nullable=False),
        sa.Column("compte_num", sa.String(20), nullable=False),
        sa.Column("compte_lib", sa.String(255), nullable=False),
        sa.Column("comp_aux_num", sa.String(20), nullable=False, server_default=""),
        sa.Column("comp_aux_lib", sa.String(255), nullable=False, server_default=""),
        sa.Column("piece_ref", sa.String(100), nullable=False),
        sa.Column("piece_date", sa.Date, nullable=False),
        sa.Column("ecriture_lib", sa.String(255), nullable=False),
        sa.Column("debit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("ecriture_let", sa.String(10), nullable=False, server_default=""),
        sa.Column("date_let", sa.Date, nullable=True),
        sa.Column("valid_date", sa.Date, nullable=False),
        sa.Column("montantdevise", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("idevise", sa.String(3), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_grand_livre_tenant_date", "grand_livre", ["tenant_id", "ecriture_date"])
    op.create_index("ix_grand_livre_tenant_compte", "grand_livre", ["tenant_id", "compte_num"])

    op.execute("ALTER TABLE grand_livre ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE grand_livre FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY tenant_access ON grand_livre
        FOR ALL
        USING (
            organization_id_of_tenant(tenant_id) = current_setting('app.current_organization_id', true)::uuid
            OR EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.tenant_id = grand_livre.tenant_id
                  AND m.user_id = current_setting('app.current_user_id', true)::uuid
            )
        )
    """)

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON grand_livre TO comptis_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_access ON grand_livre")
    op.drop_index("ix_grand_livre_tenant_compte", "grand_livre")
    op.drop_index("ix_grand_livre_tenant_date", "grand_livre")
    op.drop_table("grand_livre")
