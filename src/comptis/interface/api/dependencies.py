import functools
import os
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select as sa_select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comptis.application.auth.exceptions import InvalidTokenError, TokenExpiredError
from comptis.infrastructure.auth.api_key import get_org_id_for_api_key
from comptis.infrastructure.auth.jwt import JWTTokenService
from comptis.infrastructure.auth.password import BcryptPasswordHasher
from comptis.infrastructure.db.models import MembershipModel, TenantModel
from comptis.infrastructure.db.repositories import SQLAlchemyUserRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@functools.lru_cache
def _get_session_factory() -> async_sessionmaker:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncSession:
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session


def get_password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def get_token_service() -> JWTTokenService:
    return JWTTokenService()


def get_user_repository(session: AsyncSession = Depends(get_db_session)) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


async def require_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required"},
        )
    try:
        payload = get_token_service().decode(credentials.credentials)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Token has expired"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token type"},
        )
    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )
    await set_tenant_context(session, user_id=user_id)
    return user_id


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    """JWT valide + role admin dans au moins un tenant de l'org -> retourne org_id."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required"},
        )
    try:
        payload = get_token_service().decode(credentials.credentials)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Token has expired"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token type"},
        )
    try:
        user_id = UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )

    # Explicitly initialise all three GUC variables before querying.
    # PostgreSQL leaves a session-level "" for custom GUCs after the first LOCAL
    # set_config in any prior transaction on this pooled connection. Casting "" to
    # uuid in a USING clause raises InvalidTextRepresentationError. We use nil UUID
    # as a safe placeholder for org/tenant (won't match any real row), and the real
    # user_id so that the user_own_memberships policy can filter correctly.
    _NIL = "00000000-0000-0000-0000-000000000000"
    await session.execute(
        text(
            "SELECT set_config('app.current_user_id', :uid, true),"
            "       set_config('app.current_organization_id', :nil, true),"
            "       set_config('app.current_tenant_id', :nil, true)"
        ),
        {"uid": str(user_id), "nil": _NIL},
    )

    # Cherche un membership admin pour cet user -> org_id via tenant
    result = await session.execute(
        sa_select(TenantModel.organization_id)
        .join(MembershipModel, MembershipModel.tenant_id == TenantModel.id)
        .where(
            MembershipModel.user_id == user_id,
            MembershipModel.role == "admin",
        )
        .limit(1)
    )
    org_id: UUID | None = result.scalar_one_or_none()
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Admin role required"},
        )

    await set_tenant_context(session, organization_id=org_id, user_id=user_id)
    return org_id


async def require_api_key(
    raw_key: str = Security(_api_key_header),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required"},
        )
    org_id = await get_org_id_for_api_key(session, raw_key)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "Invalid API key"},
        )
    await set_tenant_context(session, organization_id=org_id)
    return org_id
