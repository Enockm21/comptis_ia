from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.interface.api.dependencies import get_db_session, require_user
from comptis.interface.api.tenancy.schemas import TenantSchema

router = APIRouter(tags=["tenancy"])


@router.get("/tenants", response_model=list[TenantSchema])
async def list_my_tenants(
    user_id: UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantSchema]:
    repo = SQLAlchemyTenantRepository(session)
    tenants = await repo.list_visible(session)
    return [TenantSchema(id=t.id, name=t.name) for t in tenants]
