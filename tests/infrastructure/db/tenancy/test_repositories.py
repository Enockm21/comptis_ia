from uuid import uuid4

import pytest

from comptis.domain.tenancy.entities import Organization, Tenant, User, Membership
from comptis.domain.tenancy.value_objects import OrgType, Role
from comptis.infrastructure.db.repositories import (
    SQLAlchemyOrganizationRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyMembershipRepository,
)
from comptis.infrastructure.db.tenant_context import set_tenant_context


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_save_and_retrieve_organization(db_session):
    repo = SQLAlchemyOrganizationRepository(db_session)
    org = Organization(name="Cabinet Test", type=OrgType.CABINET)
    await repo.save(org)
    retrieved = await repo.get_by_id(org.id)
    assert retrieved is not None
    assert retrieved.name == "Cabinet Test"
    assert retrieved.type == OrgType.CABINET


@pytest.mark.integration
async def test_save_and_retrieve_tenant(db_session):
    org_repo = SQLAlchemyOrganizationRepository(db_session)
    tenant_repo = SQLAlchemyTenantRepository(db_session)
    org = Organization(name="Org Pour Tenant", type=OrgType.PME_DIRECTE)
    await org_repo.save(org)
    await set_tenant_context(db_session, organization_id=org.id)
    tenant = Tenant(organization_id=org.id, name="PME Test")
    await tenant_repo.save(tenant)
    retrieved = await tenant_repo.get_by_id(tenant.id)
    assert retrieved is not None
    assert retrieved.name == "PME Test"


@pytest.mark.integration
async def test_list_tenants_by_organization(db_session):
    org_repo = SQLAlchemyOrganizationRepository(db_session)
    tenant_repo = SQLAlchemyTenantRepository(db_session)
    org = Organization(name="Cabinet Multi", type=OrgType.CABINET)
    await org_repo.save(org)
    await set_tenant_context(db_session, organization_id=org.id)
    t1 = Tenant(organization_id=org.id, name="Client A")
    t2 = Tenant(organization_id=org.id, name="Client B")
    await tenant_repo.save(t1)
    await tenant_repo.save(t2)
    tenants = await tenant_repo.list_by_organization(org.id)
    names = {t.name for t in tenants}
    assert "Client A" in names
    assert "Client B" in names


@pytest.mark.integration
async def test_save_and_retrieve_membership(db_session):
    org_repo = SQLAlchemyOrganizationRepository(db_session)
    user_repo = SQLAlchemyUserRepository(db_session)
    tenant_repo = SQLAlchemyTenantRepository(db_session)
    membership_repo = SQLAlchemyMembershipRepository(db_session)

    org = Organization(name="Org Membership", type=OrgType.CABINET)
    await org_repo.save(org)
    user = User(email=f"user-{uuid4()}@test.fr")
    await user_repo.save(user)
    await set_tenant_context(db_session, organization_id=org.id, user_id=user.id)
    tenant = Tenant(organization_id=org.id, name="Client Membership")
    await tenant_repo.save(tenant)
    m = Membership(user_id=user.id, tenant_id=tenant.id, role=Role.ACCOUNTANT)
    await membership_repo.save(m)
    retrieved = await membership_repo.get(user.id, tenant.id)
    assert retrieved is not None
    assert retrieved.role == Role.ACCOUNTANT
