"""add factures table for OCR-imported invoices

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("statut", sa.String(20), nullable=False, default="brouillon"),
        sa.Column("fournisseur", sa.Text, nullable=False),
        sa.Column("date_facture", sa.Date, nullable=False),
        sa.Column("numero_facture", sa.String(100), nullable=False, default=""),
        sa.Column("montant_ht", sa.Numeric(15, 2), nullable=False),
        sa.Column("taux_tva", sa.Numeric(5, 2), nullable=False, default=20),
        sa.Column("montant_tva", sa.Numeric(15, 2), nullable=False),
        sa.Column("montant_ttc", sa.Numeric(15, 2), nullable=False),
        sa.Column("compte_charge", sa.String(20), nullable=False, default="606100"),
        sa.Column("journal_code", sa.String(10), nullable=False, default="HA"),
        sa.Column("notes", sa.Text, nullable=False, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.execute("""
        ALTER TABLE factures ENABLE ROW LEVEL SECURITY;
        ALTER TABLE factures FORCE ROW LEVEL SECURITY;
        CREATE POLICY factures_tenant ON factures
            USING (tenant_id = organization_id_of_tenant());
        GRANT SELECT, INSERT, UPDATE, DELETE ON factures TO comptis_app;
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS factures_tenant ON factures")
    op.drop_table("factures")
