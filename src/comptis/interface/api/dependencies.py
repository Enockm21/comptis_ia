import functools
import os
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comptis.application.auth.exceptions import InvalidTokenError, TokenExpiredError
from comptis.infrastructure.auth.api_key import get_org_id_for_api_key
from comptis.infrastructure.auth.jwt import JWTTokenService
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
        payload = JWTTokenService().decode(credentials.credentials)
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
    user_id = UUID(payload["sub"])
    await set_tenant_context(session, user_id=user_id)
    return user_id


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
