from dataclasses import dataclass
from uuid import UUID

from comptis.domain.tenancy.entities import Membership, Organization, Tenant
from comptis.domain.tenancy.value_objects import OrgType, Role

from .ports import MembershipRepository, OrganizationRepository, TenantRepository


@dataclass
class CreateOrganization:
    repo: OrganizationRepository

    async def execute(self, name: str, type: OrgType) -> Organization:
        org = Organization(name=name, type=type)
        await self.repo.save(org)
        return org


@dataclass
class CreateTenant:
    repo: TenantRepository

    async def execute(self, organization_id: UUID, name: str) -> Tenant:
        tenant = Tenant(organization_id=organization_id, name=name)
        await self.repo.save(tenant)
        return tenant


@dataclass
class GrantMembership:
    repo: MembershipRepository

    async def execute(self, user_id: UUID, tenant_id: UUID, role: Role) -> Membership:
        membership = Membership(user_id=user_id, tenant_id=tenant_id, role=role)
        await self.repo.save(membership)
        return membership


@dataclass
class RevokeMembership:
    repo: MembershipRepository

    async def execute(self, user_id: UUID, tenant_id: UUID) -> None:
        await self.repo.delete(user_id, tenant_id)
