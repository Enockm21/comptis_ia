"""Initial schema with organizations, tenants, users, memberships and RLS

Revision ID: 0001
Revises:
Create Date: 2026-06-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- App role (non-superuser used by the application at runtime) ---
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'comptis_app') THEN
                CREATE ROLE comptis_app WITH LOGIN PASSWORD 'app_secret';
            END IF;
        END $$;
    """)

    # --- Tables ---
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )

    # --- Enable RLS on tenant-scoped tables ---
    for table in ("tenants", "memberships"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # --- RLS policies on tenants ---
    # Path 1: API key (machine) — org owns the tenant
    op.execute("""
        CREATE POLICY org_access ON tenants
        FOR ALL
        USING (
            organization_id = current_setting('app.current_organization_id', true)::uuid
        )
    """)
    # Path 2: Human user — explicit membership exists
    op.execute("""
        CREATE POLICY membership_access ON tenants
        FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM memberships m
                WHERE m.tenant_id = tenants.id
                  AND m.user_id = current_setting('app.current_user_id', true)::uuid
            )
        )
    """)

    # Helper function for memberships RLS
    op.execute("""
        CREATE OR REPLACE FUNCTION organization_id_of_tenant(p_tenant_id uuid)
        RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER AS $$
            SELECT organization_id FROM tenants WHERE id = p_tenant_id
        $$;
    """)

    # --- RLS policy on memberships ---
    op.execute("""
        CREATE POLICY user_own_memberships ON memberships
        FOR ALL
        USING (
            user_id = current_setting('app.current_user_id', true)::uuid
            OR organization_id_of_tenant(tenant_id) = current_setting('app.current_organization_id', true)::uuid
        )
    """)

    # --- Grants to comptis_app ---
    op.execute("GRANT USAGE ON SCHEMA public TO comptis_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO comptis_app")
    op.execute("GRANT EXECUTE ON FUNCTION organization_id_of_tenant(uuid) TO comptis_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS membership_access ON tenants")
    op.execute("DROP POLICY IF EXISTS org_access ON tenants")
    op.execute("DROP POLICY IF EXISTS user_own_memberships ON memberships")
    op.execute("DROP FUNCTION IF EXISTS organization_id_of_tenant(uuid)")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("tenants")
    op.drop_table("organizations")
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM comptis_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM comptis_app")
    op.execute("DROP ROLE IF EXISTS comptis_app")
