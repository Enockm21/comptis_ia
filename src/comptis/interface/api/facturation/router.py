from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.facturation.use_cases import AnalyserFactureOCR, FactureExtraite
from comptis.infrastructure.db.facturation_repository import SQLAlchemyFactureRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/facturation", tags=["facturation"])


async def _set_ctx(tenant_id: uuid.UUID, user_id: uuid.UUID, session: AsyncSession):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id)
    return tenant


# ── OCR analyse ───────────────────────────────────────────────────────────────

class FactureExtraiteSchema(BaseModel):
    fournisseur: str
    date_facture: date
    numero_facture: str
    montant_ht: Decimal
    taux_tva: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    compte_charge: str
    journal_code: str
    notes: str


@router.post("/analyser", response_model=FactureExtraiteSchema)
async def analyser_facture(
    tenant_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> FactureExtraiteSchema:
    await _set_ctx(tenant_id, user_id, session)
    content = await file.read()
    media_type = file.content_type or "image/jpeg"
    try:
        result: FactureExtraite = await AnalyserFactureOCR().execute(content, media_type)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"OCR échoué : {exc}") from exc
    return FactureExtraiteSchema(
        fournisseur=result.fournisseur,
        date_facture=result.date_facture,
        numero_facture=result.numero_facture,
        montant_ht=result.montant_ht,
        taux_tva=result.taux_tva,
        montant_tva=result.montant_tva,
        montant_ttc=result.montant_ttc,
        compte_charge=result.compte_charge,
        journal_code=result.journal_code,
        notes=result.notes,
    )


# ── Save facture ──────────────────────────────────────────────────────────────

class SaveFactureRequest(BaseModel):
    fournisseur: str
    date_facture: date
    numero_facture: str = ""
    montant_ht: Decimal
    taux_tva: Decimal = Decimal("20")
    montant_tva: Decimal
    montant_ttc: Decimal
    compte_charge: str = "606100"
    journal_code: str = "HA"
    notes: str = ""


class FactureSchema(BaseModel):
    id: uuid.UUID
    statut: str
    fournisseur: str
    date_facture: date
    numero_facture: str
    montant_ht: Decimal
    taux_tva: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    compte_charge: str
    journal_code: str
    notes: str
    created_at: datetime


@router.post("/factures", response_model=FactureSchema)
async def save_facture(
    body: SaveFactureRequest,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> FactureSchema:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureRepository(session)
    obj = await repo.save({
        "tenant_id": tenant_id,
        **body.model_dump(),
    })
    return FactureSchema(
        id=obj.id,
        statut=obj.statut,
        fournisseur=obj.fournisseur,
        date_facture=obj.date_facture,
        numero_facture=obj.numero_facture,
        montant_ht=obj.montant_ht,
        taux_tva=obj.taux_tva,
        montant_tva=obj.montant_tva,
        montant_ttc=obj.montant_ttc,
        compte_charge=obj.compte_charge,
        journal_code=obj.journal_code,
        notes=obj.notes,
        created_at=obj.created_at,
    )


@router.get("/factures", response_model=list[FactureSchema])
async def list_factures(
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[FactureSchema]:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureRepository(session)
    rows = await repo.list_by_tenant(tenant_id)
    return [
        FactureSchema(
            id=r.id, statut=r.statut, fournisseur=r.fournisseur,
            date_facture=r.date_facture, numero_facture=r.numero_facture,
            montant_ht=r.montant_ht, taux_tva=r.taux_tva,
            montant_tva=r.montant_tva, montant_ttc=r.montant_ttc,
            compte_charge=r.compte_charge, journal_code=r.journal_code,
            notes=r.notes, created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/factures/{facture_id}", status_code=204)
async def delete_facture(
    facture_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureRepository(session)
    await repo.delete(facture_id, tenant_id)
