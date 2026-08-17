from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyCompteComptableRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/plan-comptable", tags=["plan-comptable"])


class CompteSchema(BaseModel):
    id: uuid.UUID
    numero: str
    libelle: str
    classe: int


@router.get("", response_model=list[CompteSchema])
async def list_plan_comptable(
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CompteSchema]:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id)
    repo = SQLAlchemyCompteComptableRepository(session)
    comptes = await repo.list_by_tenant(tenant_id)
    return [CompteSchema(id=c.id, numero=c.numero, libelle=c.libelle, classe=c.classe) for c in comptes]
