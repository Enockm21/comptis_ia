"""add notes_frais table

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notes_frais",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, default="soumis"),
        sa.Column("date_depense", sa.Date, nullable=False),
        sa.Column("fournisseur", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False, default=""),
        sa.Column("montant_ht", sa.Numeric(15, 2), nullable=False),
        sa.Column("taux_tva", sa.Numeric(5, 2), nullable=False, default=20),
        sa.Column("montant_tva", sa.Numeric(15, 2), nullable=False),
        sa.Column("montant_ttc", sa.Numeric(15, 2), nullable=False),
        sa.Column("compte_charge", sa.String(20), nullable=False, default="625000"),
        sa.Column("categorie", sa.String(100), nullable=False, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.execute("""
        ALTER TABLE notes_frais ENABLE ROW LEVEL SECURITY;
        ALTER TABLE notes_frais FORCE ROW LEVEL SECURITY;
        CREATE POLICY notes_frais_tenant ON notes_frais
            USING (tenant_id = organization_id_of_tenant());
        GRANT SELECT, INSERT, UPDATE, DELETE ON notes_frais TO comptis_app;
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notes_frais_tenant ON notes_frais")
    op.drop_table("notes_frais")
