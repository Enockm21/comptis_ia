from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyEcritureRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/ecritures", tags=["ecritures"])


class EcritureSchema(BaseModel):
    id: uuid.UUID
    transaction_id: str
    facture_id: str
    montant: Decimal
    date: date
    compte_id: uuid.UUID | None
    statut: str
    created_at: str


@router.get("", response_model=list[EcritureSchema])
async def list_ecritures(
    tenant_id: uuid.UUID = Query(...),
    statut: str | None = Query(None),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[EcritureSchema]:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id)
    repo = SQLAlchemyEcritureRepository(session)
    ecritures = await repo.list_by_tenant(tenant_id, statut=statut)
    return [
        EcritureSchema(
            id=e.id,
            transaction_id=e.transaction_id,
            facture_id=e.facture_id,
            montant=e.montant,
            date=e.date,
            compte_id=e.compte_id,
            statut=e.statut.value,
            created_at=e.created_at.isoformat(),
        )
        for e in ecritures
    ]
