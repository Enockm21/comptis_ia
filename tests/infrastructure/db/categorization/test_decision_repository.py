from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationDecision
from comptis.domain.categorization.value_objects import CategorizationStatut
from comptis.infrastructure.db.categorization_decisions import SQLAlchemyCategorizationDecisionRepository

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


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_user(admin_engine):
    # categorization_decisions.validated_by has a real FK to users.id, so exercising the
    # "human validated" path needs an actual row there, not just any UUID.
    user_id = uuid4()
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, created_at) "
                    "VALUES (:id, :email, :password_hash, now())"
                ),
                {"id": str(user_id), "email": f"{user_id}@example.com", "password_hash": "x"},
            )
    return user_id


@pytest.mark.integration
async def test_save_and_get_by_ecriture(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationDecisionRepository(db_session)

    ecriture_id = uuid4()
    decision = CategorizationDecision(
        id=uuid4(), tenant_id=tenant_id, ecriture_id=ecriture_id, compte_code="626100",
        statut=CategorizationStatut.AUTO_VALIDATED, confidence=0.9, validated_by=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    await repo.save(decision)
    fetched = await repo.get_by_ecriture(ecriture_id)
    assert fetched is not None
    assert fetched.compte_code == "626100"
    assert fetched.statut == CategorizationStatut.AUTO_VALIDATED


@pytest.mark.integration
async def test_save_upserts_by_ecriture(db_session: AsyncSession, seeded_tenant, seeded_user):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationDecisionRepository(db_session)

    ecriture_id = uuid4()
    original_id = uuid4()
    pending = CategorizationDecision(
        id=original_id, tenant_id=tenant_id, ecriture_id=ecriture_id, compte_code="626100",
        statut=CategorizationStatut.PENDING_REVIEW, confidence=0.4, validated_by=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    await repo.save(pending)

    validated_by = seeded_user
    validated = CategorizationDecision(
        id=original_id, tenant_id=tenant_id, ecriture_id=ecriture_id, compte_code="613500",
        statut=CategorizationStatut.HUMAN_VALIDATED, confidence=1.0, validated_by=validated_by,
        created_at=pending.created_at,
    )
    await repo.save(validated)

    fetched = await repo.get_by_ecriture(ecriture_id)
    assert fetched.statut == CategorizationStatut.HUMAN_VALIDATED
    assert fetched.compte_code == "613500"
    assert fetched.validated_by == validated_by


@pytest.mark.integration
async def test_get_by_ecriture_none(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationDecisionRepository(db_session)
    result = await repo.get_by_ecriture(uuid4())
    assert result is None
