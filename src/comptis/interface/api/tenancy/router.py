from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.interface.api.dependencies import get_db_session, require_user
from comptis.interface.api.tenancy.schemas import TenantInfoUpdate, TenantSchema

router = APIRouter(tags=["tenancy"])


@router.get("/tenants", response_model=list[TenantSchema])
async def list_my_tenants(
    user_id: UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantSchema]:
    repo = SQLAlchemyTenantRepository(session)
    tenants = await repo.list_visible(session)
    return [
        TenantSchema(
            id=t.id,
            name=t.name,
            siret=t.siret,
            numero_tva=t.numero_tva,
            adresse=t.adresse,
            code_postal_ville=t.code_postal_ville,
        )
        for t in tenants
    ]


@router.patch("/tenants/{tenant_id}/info", response_model=TenantSchema)
async def update_tenant_info(
    tenant_id: UUID,
    body: TenantInfoUpdate,
    user_id: UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> TenantSchema:
    repo = SQLAlchemyTenantRepository(session)
    tenant = await repo.update_info(
        tenant_id,
        siret=body.siret,
        numero_tva=body.numero_tva,
        adresse=body.adresse,
        code_postal_ville=body.code_postal_ville,
    )
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await session.commit()
    return TenantSchema(
        id=tenant.id,
        name=tenant.name,
        siret=tenant.siret,
        numero_tva=tenant.numero_tva,
        adresse=tenant.adresse,
        code_postal_ville=tenant.code_postal_ville,
    )
