from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.rapprochement.entities import ReconciliationPattern
from comptis.infrastructure.db.reconciliation_patterns import SQLAlchemyReconciliationPatternRepository

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_tenant(admin_engine):
    """Create an org + tenant using the admin (superuser) engine and return the tenant_id."""
    from uuid import uuid4
    from sqlalchemy.ext.asyncio import AsyncSession

    org_id = uuid4()
    tenant_id = uuid4()
    # admin_engine is a superuser — bypasses RLS, no context variables needed.
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text(
                    "INSERT INTO organizations (id, name, type, created_at) "
                    "VALUES (:id, :name, :type, now())"
                ),
                {"id": str(org_id), "name": "Test Org", "type": "cabinet"},
            )
            await session.execute(
                text(
                    "INSERT INTO tenants (id, organization_id, name, created_at) "
                    "VALUES (:id, :org_id, :name, now())"
                ),
                {"id": str(tenant_id), "org_id": str(org_id), "name": "Test Tenant"},
            )
    return tenant_id, org_id


async def _set_rls_context(session: AsyncSession, org_id) -> None:
    """Set both RLS context variables required for reconciliation_patterns access.

    The rp_org_isolation policy checks app.organization_id; its subquery against
    tenants is also subject to tenants' own RLS (org_access) which checks
    app.current_organization_id.  Both must be set for INSERT/SELECT to succeed.
    """
    for name in ("app.organization_id", "app.current_organization_id"):
        await session.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": name, "value": str(org_id)},
        )


@pytest.mark.integration
async def test_upsert_new_pattern(db_session: AsyncSession, seeded_tenant, admin_engine):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyReconciliationPatternRepository(db_session)

    pattern = ReconciliationPattern(
        tenant_id=tenant_id,
        libelle_pattern="FACTURE ABC",
        fournisseur="ABC SARL",
        montant_approx=Decimal("100.00"),
        occurrence_count=1,
        last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    saved = await repo.upsert(pattern)
    assert saved.libelle_pattern == "FACTURE ABC"
    assert saved.occurrence_count == 1


@pytest.mark.integration
async def test_upsert_increments_count(db_session: AsyncSession, seeded_tenant, admin_engine):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyReconciliationPatternRepository(db_session)

    pattern = ReconciliationPattern(
        tenant_id=tenant_id,
        libelle_pattern="VIREMENT XYZ",
        fournisseur="XYZ SAS",
        montant_approx=Decimal("200.00"),
        occurrence_count=1,
        last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await repo.upsert(pattern)
    updated = await repo.upsert(pattern)
    assert updated.occurrence_count == 2


@pytest.mark.integration
async def test_find_by_libelle_none(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyReconciliationPatternRepository(db_session)
    result = await repo.find_by_libelle(tenant_id, "NONEXISTENT")
    assert result is None
