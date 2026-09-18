"""add factures_client and lignes_facture_client tables

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "factures_client",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("type", sa.String(10), nullable=False, default="facture"),
        sa.Column("statut", sa.String(20), nullable=False, default="brouillon"),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("date_emission", sa.Date, nullable=False),
        sa.Column("date_echeance", sa.Date, nullable=True),
        sa.Column("client_nom", sa.Text, nullable=False),
        sa.Column("client_adresse", sa.Text, nullable=False, default=""),
        sa.Column("client_email", sa.String(255), nullable=False, default=""),
        sa.Column("notes", sa.Text, nullable=False, default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    op.create_table(
        "lignes_facture_client",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("facture_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("quantite", sa.Numeric(10, 3), nullable=False, default=1),
        sa.Column("prix_unitaire", sa.Numeric(15, 2), nullable=False),
        sa.Column("taux_tva", sa.Numeric(5, 2), nullable=False, default=20),
        sa.Column("ordre", sa.Integer, nullable=False, default=0),
    )

    op.execute("""
        ALTER TABLE factures_client ENABLE ROW LEVEL SECURITY;
        ALTER TABLE factures_client FORCE ROW LEVEL SECURITY;
        CREATE POLICY faccli_tenant ON factures_client
            USING (tenant_id = organization_id_of_tenant());
        GRANT SELECT, INSERT, UPDATE, DELETE ON factures_client TO comptis_app;

        ALTER TABLE lignes_facture_client ENABLE ROW LEVEL SECURITY;
        ALTER TABLE lignes_facture_client FORCE ROW LEVEL SECURITY;
        CREATE POLICY lignesfaccli_tenant ON lignes_facture_client
            USING (tenant_id = organization_id_of_tenant());
        GRANT SELECT, INSERT, UPDATE, DELETE ON lignes_facture_client TO comptis_app;
    """)


def downgrade() -> None:
    op.execute("""
        DROP POLICY IF EXISTS lignesfaccli_tenant ON lignes_facture_client;
        DROP POLICY IF EXISTS faccli_tenant ON factures_client;
    """)
    op.drop_table("lignes_facture_client")
    op.drop_table("factures_client")
