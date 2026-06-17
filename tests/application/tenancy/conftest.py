import pytest
from uuid import UUID

from comptis.domain.tenancy.entities import Membership, Organization, Tenant, User


class InMemoryOrganizationRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Organization] = {}

    async def save(self, org: Organization) -> None:
        self._store[org.id] = org

    async def get_by_id(self, id: UUID) -> Organization | None:
        return self._store.get(id)


class InMemoryTenantRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Tenant] = {}

    async def save(self, tenant: Tenant) -> None:
        self._store[tenant.id] = tenant

    async def get_by_id(self, id: UUID) -> Tenant | None:
        return self._store.get(id)

    async def list_by_organization(self, org_id: UUID) -> list[Tenant]:
        return [t for t in self._store.values() if t.organization_id == org_id]


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}

    async def save(self, user: User) -> None:
        self._by_email[user.email] = user

    async def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email)


class InMemoryMembershipRepository:
    def __init__(self) -> None:
        self._store: dict[tuple[UUID, UUID], Membership] = {}

    async def save(self, membership: Membership) -> None:
        self._store[(membership.user_id, membership.tenant_id)] = membership

    async def delete(self, user_id: UUID, tenant_id: UUID) -> None:
        self._store.pop((user_id, tenant_id), None)

    async def get(self, user_id: UUID, tenant_id: UUID) -> Membership | None:
        return self._store.get((user_id, tenant_id))


@pytest.fixture
def org_repo() -> InMemoryOrganizationRepository:
    return InMemoryOrganizationRepository()


@pytest.fixture
def tenant_repo() -> InMemoryTenantRepository:
    return InMemoryTenantRepository()


@pytest.fixture
def user_repo() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def membership_repo() -> InMemoryMembershipRepository:
    return InMemoryMembershipRepository()
