"""Add reconciliation_patterns table

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_patterns",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("libelle_pattern", sa.String(255), nullable=False),
        sa.Column("fournisseur", sa.String(255), nullable=False),
        sa.Column("montant_approx", sa.Numeric(12, 2), nullable=False),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "libelle_pattern", "fournisseur",
            name="uq_rp_tenant_libelle_fournisseur",
        ),
    )
    op.create_index(
        "ix_reconciliation_patterns_tenant_libelle",
        "reconciliation_patterns",
        ["tenant_id", "libelle_pattern"],
    )
    op.execute("ALTER TABLE reconciliation_patterns ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY rp_org_isolation ON reconciliation_patterns
            USING (
                tenant_id IN (
                    SELECT id FROM tenants
                    WHERE organization_id = current_setting('app.organization_id', true)::uuid
                )
            )
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON reconciliation_patterns TO comptis_app"
    )


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON reconciliation_patterns FROM comptis_app")
    op.execute("DROP POLICY IF EXISTS rp_org_isolation ON reconciliation_patterns")
    op.drop_index("ix_reconciliation_patterns_tenant_libelle", table_name="reconciliation_patterns")
    op.drop_table("reconciliation_patterns")
