"""Fix plan_comptable and ecritures RLS — guard against empty GUC string

When app.current_tenant_id is first referenced in a session via set_config(…, true)
(transaction-local), Postgres initialises the session-level GUC to '' (empty string).
After the transaction commits or rolls back the local override is removed, leaving the
session-level '' in place.  Subsequent queries in the same pooled connection then call
current_setting('app.current_tenant_id', true) which returns '', and ''::uuid raises
InvalidTextRepresentationError.

The fix is the same pattern used in all 0001 tenants/memberships policies: wrap with
NULLIF so that '' is treated as NULL.  NULL::uuid = NULL, and column = NULL is FALSE
— the row is hidden — rather than an error.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("plan_comptable", "ecritures"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
                USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
            """
        )


def downgrade() -> None:
    for table in ("plan_comptable", "ecritures"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )
