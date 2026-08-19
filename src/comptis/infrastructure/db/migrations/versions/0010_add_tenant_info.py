"""add company info fields to tenants

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-19
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("siret", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("numero_tva", sa.String(20), nullable=True))
    op.add_column("tenants", sa.Column("adresse", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("code_postal_ville", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "code_postal_ville")
    op.drop_column("tenants", "adresse")
    op.drop_column("tenants", "numero_tva")
    op.drop_column("tenants", "siret")
