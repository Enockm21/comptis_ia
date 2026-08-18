"""add reconciliation_runs table

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-18
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, nullable=False, index=True),
        sa.Column("date_debut", sa.Date, nullable=False),
        sa.Column("date_fin", sa.Date, nullable=False),
        sa.Column("total_transactions", sa.Integer, nullable=False, default=0),
        sa.Column("total_rapprochees", sa.Integer, nullable=False, default=0),
        sa.Column("total_ecarts", sa.Integer, nullable=False, default=0),
        sa.Column("total_non_rapprochees", sa.Integer, nullable=False, default=0),
        sa.Column("statut", sa.String(20), nullable=False, default="en_cours"),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.execute("""
        ALTER TABLE reconciliation_runs ENABLE ROW LEVEL SECURITY;

        CREATE POLICY reconciliation_runs_tenant_isolation ON reconciliation_runs
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid
        );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS reconciliation_runs_tenant_isolation ON reconciliation_runs")
    op.drop_table("reconciliation_runs")
