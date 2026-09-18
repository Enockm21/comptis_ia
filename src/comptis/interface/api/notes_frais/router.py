from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.notes_frais.use_cases import AnalyserDepenseOCR
from comptis.infrastructure.db.models import NoteFraisModel
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/notes-frais", tags=["notes-frais"])


async def _set_ctx(tenant_id: uuid.UUID, user_id: uuid.UUID, session: AsyncSession):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(404, "Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id,
                             tenant_id=tenant_id, user_id=user_id)
    return tenant


class DepenseSchema(BaseModel):
    date_depense: date
    fournisseur: str
    description: str
    montant_ht: Decimal
    taux_tva: Decimal
    montant_tva: Decimal
    montant_ttc: Decimal
    compte_charge: str
    categorie: str


class NoteFraisSchema(DepenseSchema):
    id: uuid.UUID
    statut: str
    submitted_by: uuid.UUID
    created_at: datetime


class CreateNoteRequest(DepenseSchema):
    pass


@router.post("/analyser", response_model=DepenseSchema)
async def analyser_depense(
    tenant_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> DepenseSchema:
    await _set_ctx(tenant_id, user_id, session)
    content = await file.read()
    try:
        r = await AnalyserDepenseOCR().execute(content, file.content_type or "image/jpeg")
    except Exception as exc:
        raise HTTPException(422, f"OCR échoué : {exc}") from exc
    return DepenseSchema(
        date_depense=r.date_depense, fournisseur=r.fournisseur,
        description=r.description, montant_ht=r.montant_ht,
        taux_tva=r.taux_tva, montant_tva=r.montant_tva,
        montant_ttc=r.montant_ttc, compte_charge=r.compte_charge,
        categorie=r.categorie,
    )


@router.post("", response_model=NoteFraisSchema)
async def create_note(
    body: CreateNoteRequest,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> NoteFraisSchema:
    await _set_ctx(tenant_id, user_id, session)
    from uuid import uuid4
    from datetime import timezone
    obj = NoteFraisModel(
        id=uuid4(), tenant_id=tenant_id, submitted_by=user_id,
        statut="soumis", **body.model_dump(),
    )
    session.add(obj)
    await session.flush()
    return _to_schema(obj)


@router.get("", response_model=list[NoteFraisSchema])
async def list_notes(
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[NoteFraisSchema]:
    await _set_ctx(tenant_id, user_id, session)
    result = await session.execute(
        select(NoteFraisModel)
        .where(NoteFraisModel.tenant_id == tenant_id)
        .order_by(NoteFraisModel.date_depense.desc())
    )
    return [_to_schema(r) for r in result.scalars().all()]


@router.patch("/{note_id}/statut", response_model=NoteFraisSchema)
async def update_statut(
    note_id: uuid.UUID,
    statut: str = Query(...),
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> NoteFraisSchema:
    await _set_ctx(tenant_id, user_id, session)
    await session.execute(
        update(NoteFraisModel)
        .where(NoteFraisModel.id == note_id, NoteFraisModel.tenant_id == tenant_id)
        .values(statut=statut)
    )
    result = await session.execute(
        select(NoteFraisModel).where(NoteFraisModel.id == note_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(404, "Note introuvable")
    return _to_schema(obj)


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await _set_ctx(tenant_id, user_id, session)
    await session.execute(
        delete(NoteFraisModel).where(
            NoteFraisModel.id == note_id,
            NoteFraisModel.tenant_id == tenant_id,
        )
    )


def _to_schema(obj: NoteFraisModel) -> NoteFraisSchema:
    return NoteFraisSchema(
        id=obj.id, statut=obj.statut, submitted_by=obj.submitted_by,
        created_at=obj.created_at, date_depense=obj.date_depense,
        fournisseur=obj.fournisseur, description=obj.description,
        montant_ht=obj.montant_ht, taux_tva=obj.taux_tva,
        montant_tva=obj.montant_tva, montant_ttc=obj.montant_ttc,
        compte_charge=obj.compte_charge, categorie=obj.categorie,
    )
