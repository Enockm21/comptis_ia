from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.comptabilite.use_cases import (
    CalculerBalance,
    CalculerBilan,
    CalculerResultat,
    ExporterFEC,
    ImporterFEC,
)
from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyGrandLivreRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/comptabilite", tags=["comptabilite"])


async def _get_tenant_and_set_context(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    session: AsyncSession,
):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(
        session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id
    )
    return tenant


# ── FEC import ─────────────────────────────────────────────────────────────────

class FECImportResponse(BaseModel):
    lignes_importees: int


@router.post("/fec/import", response_model=FECImportResponse)
async def import_fec(
    tenant_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> FECImportResponse:
    await _get_tenant_and_set_context(tenant_id, user_id, session)
    content = await file.read()
    repo = SQLAlchemyGrandLivreRepository(session)
    n = await ImporterFEC(repo=repo).execute(tenant_id, content)
    return FECImportResponse(lignes_importees=n)


# ── FEC export ─────────────────────────────────────────────────────────────────

@router.get("/fec/export")
async def export_fec(
    tenant_id: uuid.UUID = Query(...),
    date_debut: date | None = Query(None),
    date_fin: date | None = Query(None),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    tenant = await _get_tenant_and_set_context(tenant_id, user_id, session)
    repo = SQLAlchemyGrandLivreRepository(session)
    csv_bytes = await ExporterFEC(repo=repo).execute(tenant_id, date_debut, date_fin)
    siren = (tenant.siret or "000000000")[:9]
    period = f"{date_debut or 'all'}"
    filename = f"FEC{siren}{period}.txt"
    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Balance des comptes ────────────────────────────────────────────────────────

class PosteBalanceSchema(BaseModel):
    compte_num: str
    compte_lib: str
    total_debit: Decimal
    total_credit: Decimal
    solde_debiteur: Decimal
    solde_crediteur: Decimal


@router.get("/balance", response_model=list[PosteBalanceSchema])
async def balance_des_comptes(
    tenant_id: uuid.UUID = Query(...),
    date_debut: date | None = Query(None),
    date_fin: date | None = Query(None),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[PosteBalanceSchema]:
    await _get_tenant_and_set_context(tenant_id, user_id, session)
    repo = SQLAlchemyGrandLivreRepository(session)
    postes = await CalculerBalance(repo=repo).execute(tenant_id, date_debut, date_fin)
    return [
        PosteBalanceSchema(
            compte_num=p.compte_num, compte_lib=p.compte_lib,
            total_debit=p.total_debit, total_credit=p.total_credit,
            solde_debiteur=p.solde_debiteur, solde_crediteur=p.solde_crediteur,
        )
        for p in postes
    ]


# ── Bilan ──────────────────────────────────────────────────────────────────────

class PosteBilanSchema(BaseModel):
    classe: int
    libelle: str
    montant: Decimal
    side: str


@router.get("/bilan", response_model=list[PosteBilanSchema])
async def bilan(
    tenant_id: uuid.UUID = Query(...),
    date_cloture: date = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[PosteBilanSchema]:
    await _get_tenant_and_set_context(tenant_id, user_id, session)
    repo = SQLAlchemyGrandLivreRepository(session)
    postes = await CalculerBilan(repo=repo).execute(tenant_id, date_cloture)
    return [PosteBilanSchema(**p.__dict__) for p in postes]


# ── Compte de résultat ─────────────────────────────────────────────────────────

class PosteResultatSchema(BaseModel):
    classe: int
    libelle: str
    montant: Decimal
    nature: str


class ResultatResponse(BaseModel):
    postes: list[PosteResultatSchema]
    resultat_net: Decimal


@router.get("/resultat", response_model=ResultatResponse)
async def compte_de_resultat(
    tenant_id: uuid.UUID = Query(...),
    date_debut: date = Query(...),
    date_fin: date = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> ResultatResponse:
    await _get_tenant_and_set_context(tenant_id, user_id, session)
    repo = SQLAlchemyGrandLivreRepository(session)
    postes, resultat = await CalculerResultat(repo=repo).execute(tenant_id, date_debut, date_fin)
    return ResultatResponse(
        postes=[PosteResultatSchema(**p.__dict__) for p in postes],
        resultat_net=resultat,
    )
