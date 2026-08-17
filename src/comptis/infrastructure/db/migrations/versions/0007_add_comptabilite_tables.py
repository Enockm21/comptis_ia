"""Add plan_comptable (per-tenant chart of accounts) and ecritures tables with RLS

plan_comptable: per-tenant chart of accounts imported from PNiCompta.
  Distinct from the global `comptes_pcg` (PCG reference table seeded in 0006).
  RLS uses NULLIF(current_setting('app.current_tenant_id', true), '')::uuid to
  guard against asyncpg pooled connections leaving '' in the GUC after a
  transaction ends.

ecritures: accounting entries created when a reconciliation match is confirmed.
  compte_id FK references plan_comptable (the tenant's actual chart, not the
  global PCG reference which serves the categorization engine).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_comptable",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("classe", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "numero", name="uq_plan_comptable_tenant_numero"),
    )
    op.create_table(
        "ecritures",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", sa.String(64), nullable=False),
        sa.Column("facture_id", sa.String(64), nullable=False),
        sa.Column("montant", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("compte_id", sa.Uuid, sa.ForeignKey("plan_comptable.id", ondelete="SET NULL"), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="a_categoriser"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_ecritures_tenant_transaction"),
    )

    for table in ("plan_comptable", "ecritures"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
        """)
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO comptis_app")


def downgrade() -> None:
    for table in ("plan_comptable", "ecritures"):
        op.execute(f"REVOKE ALL PRIVILEGES ON {table} FROM comptis_app")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("ecritures")
    op.drop_table("plan_comptable")
