"""add ca3_declarations table

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ca3_declarations",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("periode_debut", sa.Date(), nullable=False),
        sa.Column("periode_fin", sa.Date(), nullable=False),
        sa.Column("raison_sociale", sa.String(255), nullable=True),
        sa.Column("adresse", sa.String(255), nullable=True),
        sa.Column("code_postal_ville", sa.String(100), nullable=True),
        sa.Column("siret", sa.String(20), nullable=True),
        sa.Column("numero_tva", sa.String(25), nullable=True),
        sa.Column("a1_ventes", sa.Numeric(15, 2), nullable=True),
        sa.Column("l08_base", sa.Numeric(15, 2), nullable=True),
        sa.Column("l08_taxe", sa.Numeric(15, 2), nullable=True),
        sa.Column("l09_base", sa.Numeric(15, 2), nullable=True),
        sa.Column("l09_taxe", sa.Numeric(15, 2), nullable=True),
        sa.Column("l9b_base", sa.Numeric(15, 2), nullable=True),
        sa.Column("l9b_taxe", sa.Numeric(15, 2), nullable=True),
        sa.Column("l16_brute", sa.Numeric(15, 2), nullable=True),
        sa.Column("l19_immos", sa.Numeric(15, 2), nullable=True),
        sa.Column("l20_autres", sa.Numeric(15, 2), nullable=True),
        sa.Column("l22_report", sa.Numeric(15, 2), nullable=True),
        sa.Column("l23_total_ded", sa.Numeric(15, 2), nullable=True),
        sa.Column("tva_due", sa.Numeric(15, 2), nullable=True),
        sa.Column("credit_tva", sa.Numeric(15, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ca3_declarations_tenant_periode", "ca3_declarations",
                    ["tenant_id", "periode_debut"])


def downgrade() -> None:
    op.drop_index("ix_ca3_declarations_tenant_periode")
    op.drop_table("ca3_declarations")
