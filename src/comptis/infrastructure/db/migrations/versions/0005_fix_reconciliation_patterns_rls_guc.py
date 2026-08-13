"""Fix reconciliation_patterns RLS policy — wrong GUC name

The rp_org_isolation policy created in 0003 reads current_setting('app.organization_id', true),
but the application only ever sets 'app.current_organization_id' (see tenant_context.py and every
other RLS policy in 0001). The mismatched GUC name means the policy never actually matches the
application's session context, so:
- SELECTs under app role silently return zero rows (pattern learning is a no-op)
- INSERTs/upserts violate the policy's implied WITH CHECK (InsufficientPrivilegeError)

This was flagged as a known pre-existing issue during the reconciliation-review-ui branch's final
review and confirmed live when running a real reconciliation.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rp_org_isolation ON reconciliation_patterns")
    op.execute(
        """
        CREATE POLICY rp_org_isolation ON reconciliation_patterns
            USING (
                tenant_id IN (
                    SELECT id FROM tenants
                    WHERE organization_id = current_setting('app.current_organization_id', true)::uuid
                )
            )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rp_org_isolation ON reconciliation_patterns")
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
