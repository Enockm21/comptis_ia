from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationPattern
from comptis.infrastructure.db.categorization_patterns import SQLAlchemyCategorizationPatternRepository
from comptis.infrastructure.db.models import CategorizationPatternModel

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_tenant(admin_engine):
    org_id = uuid4()
    tenant_id = uuid4()
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO organizations (id, name, type, created_at) VALUES (:id, :name, :type, now())"),
                {"id": str(org_id), "name": "Test Org", "type": "cabinet"},
            )
            await session.execute(
                text("INSERT INTO tenants (id, organization_id, name, created_at) VALUES (:id, :org_id, :name, now())"),
                {"id": str(tenant_id), "org_id": str(org_id), "name": "Test Tenant"},
            )
    return tenant_id, org_id


async def _set_rls_context(session: AsyncSession, org_id) -> None:
    await session.execute(
        text("SELECT set_config('app.current_organization_id', :value, true)"),
        {"value": str(org_id)},
    )


@pytest.mark.integration
async def test_upsert_new_pattern(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationPatternRepository(db_session)

    pattern = CategorizationPattern(
        tenant_id=tenant_id, libelle_pattern="BRETAGNE TELECOM", fournisseur="Bretagne Telecom",
        compte_code="626100", occurrence_count=1, last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    saved = await repo.upsert(pattern)
    assert saved.compte_code == "626100"
    assert saved.occurrence_count == 1


@pytest.mark.integration
async def test_upsert_increments_and_overrides_compte(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationPatternRepository(db_session)

    first = CategorizationPattern(
        tenant_id=tenant_id, libelle_pattern="SIEMENS", fournisseur="Siemens Lease",
        compte_code="613500", occurrence_count=1, last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await repo.upsert(first)

    corrected = CategorizationPattern(
        tenant_id=tenant_id, libelle_pattern="SIEMENS", fournisseur="Siemens Lease",
        compte_code="615500", occurrence_count=1, last_seen_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    updated = await repo.upsert(corrected)
    assert updated.occurrence_count == 2
    assert updated.compte_code == "615500"


@pytest.mark.integration
async def test_find_by_libelle_none(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationPatternRepository(db_session)
    result = await repo.find_by_libelle(tenant_id, "NONEXISTENT")
    assert result is None


@pytest.mark.integration
async def test_other_org_cannot_see_pattern(seeded_tenant, admin_engine, app_engine):
    """Seed via admin_engine (superuser, real commit, bypasses RLS) so the row genuinely
    persists — then read via app_engine scoped to a *different* org. Using db_session for
    the write here would be wrong: that fixture wraps the test in an open transaction that
    always rolls back, so a separate session would never see the row regardless of RLS,
    and the test would pass for the wrong reason."""
    tenant_id, org_id = seeded_tenant
    async with AsyncSession(admin_engine, expire_on_commit=False) as seed_session:
        async with seed_session.begin():
            seed_session.add(CategorizationPatternModel(
                id=uuid4(), tenant_id=tenant_id, libelle_pattern="ISOLATED", fournisseur="X",
                compte_code="626100", occurrence_count=1, last_seen_at=datetime.now(tz=timezone.utc),
            ))

    other_org_id = uuid4()
    async with AsyncSession(app_engine, expire_on_commit=False) as other_session:
        async with other_session.begin():
            await _set_rls_context(other_session, other_org_id)
            other_repo = SQLAlchemyCategorizationPatternRepository(other_session)
            result = await other_repo.find_by_libelle(tenant_id, "ISOLATED")
            assert result is None, "RLS leak: other org can see this org's categorization pattern"
