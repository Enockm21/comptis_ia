from uuid import uuid4

import pytest

from comptis.application.tenancy.use_cases import (
    CreateOrganization,
    CreateTenant,
    GrantMembership,
    RevokeMembership,
)
from comptis.domain.tenancy.value_objects import OrgType, Role


async def test_create_organization_persists_and_returns(org_repo):
    use_case = CreateOrganization(repo=org_repo)
    org = await use_case.execute(name="Cabinet Dupont", type=OrgType.CABINET)
    assert org.name == "Cabinet Dupont"
    assert org.type == OrgType.CABINET
    assert await org_repo.get_by_id(org.id) is not None


async def test_create_tenant_links_to_organization(tenant_repo):
    use_case = CreateTenant(repo=tenant_repo)
    org_id = uuid4()
    tenant = await use_case.execute(organization_id=org_id, name="Boulangerie Martin")
    assert tenant.name == "Boulangerie Martin"
    assert tenant.organization_id == org_id
    assert await tenant_repo.get_by_id(tenant.id) is not None


async def test_grant_membership_creates_record(membership_repo):
    use_case = GrantMembership(repo=membership_repo)
    user_id, tenant_id = uuid4(), uuid4()
    m = await use_case.execute(user_id=user_id, tenant_id=tenant_id, role=Role.ACCOUNTANT)
    assert m.role == Role.ACCOUNTANT
    stored = await membership_repo.get(user_id, tenant_id)
    assert stored is not None
    assert stored.role == Role.ACCOUNTANT


async def test_revoke_membership_removes_record(membership_repo):
    grant = GrantMembership(repo=membership_repo)
    revoke = RevokeMembership(repo=membership_repo)
    user_id, tenant_id = uuid4(), uuid4()
    await grant.execute(user_id=user_id, tenant_id=tenant_id, role=Role.VIEWER)
    await revoke.execute(user_id=user_id, tenant_id=tenant_id)
    assert await membership_repo.get(user_id, tenant_id) is None


async def test_revoke_membership_is_idempotent(membership_repo):
    revoke = RevokeMembership(repo=membership_repo)
    user_id, tenant_id = uuid4(), uuid4()
    await revoke.execute(user_id=user_id, tenant_id=tenant_id)  # no membership exists — should not raise
