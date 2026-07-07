"""
These tests verify that RLS prevents cross-tenant data leakage.
Each test creates data under one organization, then queries from
a session scoped to a different organization and asserts empty results.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.tenancy.entities import Organization, Tenant
from comptis.domain.tenancy.value_objects import OrgType
from comptis.infrastructure.db.models import TenantModel, OrganizationModel
from comptis.infrastructure.db.repositories import (
    SQLAlchemyOrganizationRepository,
    SQLAlchemyTenantRepository,
)
from comptis.infrastructure.db.tenant_context import set_tenant_context


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_org_b_cannot_see_org_a_tenants(admin_engine, app_engine):
    org_a = Organization(name="Cabinet A", type=OrgType.CABINET)
    org_b = Organization(name="Cabinet B", type=OrgType.CABINET)
    tenant_a = Tenant(organization_id=org_a.id, name="Client de A")

    # Seed via superuser (bypasses RLS) to freely insert cross-org data
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            session.add(OrganizationModel(id=org_a.id, name=org_a.name, type=org_a.type.value, created_at=org_a.created_at))
            session.add(OrganizationModel(id=org_b.id, name=org_b.name, type=org_b.type.value, created_at=org_b.created_at))
            session.add(TenantModel(id=tenant_a.id, organization_id=org_a.id, name=tenant_a.name, created_at=tenant_a.created_at))

    # Assert via comptis_app (RLS enforced): org B sees zero tenants
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            await set_tenant_context(session, organization_id=org_b.id)
            result = await session.execute(select(TenantModel))
            visible = result.scalars().all()
            assert len(visible) == 0, (
                f"RLS leak: org B can see {len(visible)} tenant(s) belonging to org A"
            )


@pytest.mark.integration
async def test_org_a_only_sees_own_tenants(admin_engine, app_engine):
    org_a = Organization(name="Cabinet Isolation A", type=OrgType.CABINET)
    org_b = Organization(name="Cabinet Isolation B", type=OrgType.CABINET)
    tenant_a1 = Tenant(organization_id=org_a.id, name="A-Client-1")
    tenant_a2 = Tenant(organization_id=org_a.id, name="A-Client-2")
    tenant_b1 = Tenant(organization_id=org_b.id, name="B-Client-1")

    # Seed via superuser — freely insert all orgs and tenants regardless of RLS
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            for org in [org_a, org_b]:
                session.add(OrganizationModel(id=org.id, name=org.name, type=org.type.value, created_at=org.created_at))
            for t in [tenant_a1, tenant_a2, tenant_b1]:
                session.add(TenantModel(id=t.id, organization_id=t.organization_id, name=t.name, created_at=t.created_at))

    # Assert via comptis_app (RLS enforced): org A sees only its two tenants
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            await set_tenant_context(session, organization_id=org_a.id)
            result = await session.execute(select(TenantModel))
            names = {t.name for t in result.scalars().all()}
            assert "A-Client-1" in names
            assert "A-Client-2" in names
            assert "B-Client-1" not in names, "RLS leak: org A can see org B tenant"


@pytest.mark.integration
async def test_no_context_returns_empty(app_engine):
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            # No context set — both RLS policies evaluate to false via missing_ok NULL
            result = await session.execute(select(TenantModel))
            assert result.scalars().all() == []
