import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.models import PlanComptableModel
from comptis.infrastructure.db.tenant_context import set_tenant_context

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_tenant_b_cannot_see_tenant_a_comptes(admin_engine, app_engine):
    from uuid import uuid4
    from sqlalchemy import text

    org_id = uuid4()
    tenant_a = uuid4()
    tenant_b = uuid4()
    compte_a = uuid4()

    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO organizations (id, name, type, created_at) VALUES (:id, 'Org', 'cabinet', now())"),
                {"id": str(org_id)},
            )
            for tid, name in [(tenant_a, "Tenant A"), (tenant_b, "Tenant B")]:
                await session.execute(
                    text("INSERT INTO tenants (id, organization_id, name, created_at) VALUES (:id, :org_id, :name, now())"),
                    {"id": str(tid), "org_id": str(org_id), "name": name},
                )
            await session.execute(
                text(
                    "INSERT INTO plan_comptable (id, tenant_id, numero, libelle, classe, created_at) "
                    "VALUES (:id, :tenant_id, '625100', 'Voyages', 6, now())"
                ),
                {"id": str(compte_a), "tenant_id": str(tenant_a)},
            )

    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            await set_tenant_context(session, tenant_id=tenant_b)
            result = await session.execute(select(PlanComptableModel))
            visible = result.scalars().all()
            assert len(visible) == 0, f"RLS leak: tenant B can see {len(visible)} compte(s) belonging to tenant A"


@pytest.mark.integration
async def test_no_tenant_context_returns_empty(app_engine):
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            result = await session.execute(select(PlanComptableModel))
            assert result.scalars().all() == []
