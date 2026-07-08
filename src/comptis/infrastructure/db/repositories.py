from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.tenancy.entities import Membership, Organization, Tenant, User
from comptis.domain.tenancy.value_objects import OrgType, Role

from .models import ApiKeyModel, MembershipModel, OrganizationModel, TenantModel, UserModel


def _org_to_domain(m: OrganizationModel) -> Organization:
    return Organization(id=m.id, name=m.name, type=OrgType(m.type), created_at=m.created_at)


def _tenant_to_domain(m: TenantModel) -> Tenant:
    return Tenant(id=m.id, organization_id=m.organization_id, name=m.name, created_at=m.created_at)


def _user_to_domain(m: UserModel) -> User:
    return User(id=m.id, email=m.email, created_at=m.created_at)


def _membership_to_domain(m: MembershipModel) -> Membership:
    return Membership(
        id=m.id, user_id=m.user_id, tenant_id=m.tenant_id,
        role=Role(m.role), created_at=m.created_at,
    )


class SQLAlchemyOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, org: Organization) -> None:
        model = OrganizationModel(id=org.id, name=org.name, type=org.type.value, created_at=org.created_at)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, id: UUID) -> Organization | None:
        result = await self._session.execute(select(OrganizationModel).where(OrganizationModel.id == id))
        model = result.scalar_one_or_none()
        return _org_to_domain(model) if model else None


class SQLAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, tenant: Tenant) -> None:
        model = TenantModel(id=tenant.id, organization_id=tenant.organization_id, name=tenant.name, created_at=tenant.created_at)
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, id: UUID) -> Tenant | None:
        result = await self._session.execute(select(TenantModel).where(TenantModel.id == id))
        model = result.scalar_one_or_none()
        return _tenant_to_domain(model) if model else None

    async def list_by_organization(self, org_id: UUID) -> list[Tenant]:
        result = await self._session.execute(
            select(TenantModel).where(TenantModel.organization_id == org_id)
        )
        return [_tenant_to_domain(m) for m in result.scalars().all()]


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: User) -> None:
        model = UserModel(id=user.id, email=user.email, created_at=user.created_at)
        self._session.add(model)
        await self._session.flush()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return _user_to_domain(model) if model else None

    async def save_with_credentials(self, user: User, password_hash: str) -> None:
        model = UserModel(
            id=user.id, email=user.email,
            password_hash=password_hash, created_at=user.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_password_hash(self, user_id: UUID) -> str | None:
        result = await self._session.execute(
            select(UserModel.password_hash).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()


class SQLAlchemyMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, membership: Membership) -> None:
        model = MembershipModel(
            id=membership.id, user_id=membership.user_id,
            tenant_id=membership.tenant_id, role=membership.role.value,
            created_at=membership.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def delete(self, user_id: UUID, tenant_id: UUID) -> None:
        result = await self._session.execute(
            select(MembershipModel).where(
                MembershipModel.user_id == user_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def get(self, user_id: UUID, tenant_id: UUID) -> Membership | None:
        result = await self._session.execute(
            select(MembershipModel).where(
                MembershipModel.user_id == user_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        model = result.scalar_one_or_none()
        return _membership_to_domain(model) if model else None


class SQLAlchemyApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, api_key_id: UUID, organization_id: UUID, name: str, key_hash: str) -> None:
        from datetime import datetime, timezone
        model = ApiKeyModel(
            id=api_key_id,
            organization_id=organization_id,
            name=name,
            key_hash=key_hash,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(model)
        await self._session.flush()
