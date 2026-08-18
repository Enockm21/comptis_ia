from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.tva.use_cases import ComputeTVA
from comptis.domain.tva.entities import TVADeclaration
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.infrastructure.db.tva_repository import SQLAlchemyTVARepository
from comptis.infrastructure.mcp.client_factory import build_mcp_client_for_org
from comptis.interface.api.dependencies import get_db_session, require_user
from comptis.interface.api.tva.schemas import (
    TVAComputeResponse,
    TVADeclarationCreate,
    TVADeclarationResponse,
    TVALineSchema,
    TVAStatutUpdate,
)

router = APIRouter(prefix="/tva", tags=["tva"])


async def _get_tenant(tenant_id: uuid.UUID, session: AsyncSession, user_id: uuid.UUID):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id)
    return tenant


@router.get("/compute", response_model=TVAComputeResponse)
async def compute_tva(
    tenant_id: uuid.UUID,
    date_debut: date,
    date_fin: date,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> TVAComputeResponse:
    tenant = await _get_tenant(tenant_id, session, user_id)
    mcp_client = await build_mcp_client_for_org(tenant.organization_id, session)
    summary = await ComputeTVA(mcp_client).execute(tenant_id, date_debut, date_fin)

    return TVAComputeResponse(
        date_debut=date_debut,
        date_fin=date_fin,
        tva_collectee=summary.tva_collectee,
        tva_deductible=summary.tva_deductible,
        tva_nette=summary.tva_nette,
        est_credit=summary.est_credit,
        lignes_collectee=[TVALineSchema(taux=l.taux, base_ht=l.base_ht, montant_tva=l.montant_tva, nb_factures=l.nb_factures) for l in summary.lignes_collectee],
        lignes_deductible=[TVALineSchema(taux=l.taux, base_ht=l.base_ht, montant_tva=l.montant_tva, nb_factures=l.nb_factures) for l in summary.lignes_deductible],
    )


@router.post("/declarations", response_model=TVADeclarationResponse, status_code=201)
async def create_declaration(
    body: TVADeclarationCreate,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> TVADeclarationResponse:
    await _get_tenant(body.tenant_id, session, user_id)

    lignes = [
        *[{"type": "collectee", "taux": str(l.taux), "base_ht": str(l.base_ht), "montant_tva": str(l.montant_tva), "nb_factures": l.nb_factures} for l in body.lignes_collectee],
        *[{"type": "deductible", "taux": str(l.taux), "base_ht": str(l.base_ht), "montant_tva": str(l.montant_tva), "nb_factures": l.nb_factures} for l in body.lignes_deductible],
    ]

    declaration = TVADeclaration(
        tenant_id=body.tenant_id,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
        tva_collectee=body.tva_collectee,
        tva_deductible=body.tva_deductible,
        tva_nette=body.tva_nette,
        lignes=lignes,
        statut="brouillon",
    )

    repo = SQLAlchemyTVARepository(session)
    model = await repo.save(declaration)
    await session.commit()

    return TVADeclarationResponse(
        id=model.id,
        tenant_id=model.tenant_id,
        date_debut=model.date_debut,
        date_fin=model.date_fin,
        tva_collectee=model.tva_collectee,
        tva_deductible=model.tva_deductible,
        tva_nette=model.tva_nette,
        lignes=model.lignes,
        statut=model.statut,
        created_at=model.created_at,
        deposee_le=model.deposee_le,
        payee_le=model.payee_le,
    )


@router.get("/declarations", response_model=list[TVADeclarationResponse])
async def list_declarations(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TVADeclarationResponse]:
    await _get_tenant(tenant_id, session, user_id)
    repo = SQLAlchemyTVARepository(session)
    models = await repo.list_by_tenant(tenant_id)
    return [
        TVADeclarationResponse(
            id=m.id,
            tenant_id=m.tenant_id,
            date_debut=m.date_debut,
            date_fin=m.date_fin,
            tva_collectee=m.tva_collectee,
            tva_deductible=m.tva_deductible,
            tva_nette=m.tva_nette,
            lignes=m.lignes,
            statut=m.statut,
            created_at=m.created_at,
            deposee_le=m.deposee_le,
            payee_le=m.payee_le,
        )
        for m in models
    ]


@router.patch("/declarations/{declaration_id}/statut", response_model=TVADeclarationResponse)
async def update_statut(
    declaration_id: uuid.UUID,
    body: TVAStatutUpdate,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> TVADeclarationResponse:
    if body.statut not in {"deposee", "payee", "brouillon"}:
        raise HTTPException(status_code=422, detail="statut must be deposee, payee or brouillon")

    repo = SQLAlchemyTVARepository(session)
    model = await repo.get(declaration_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Declaration not found")

    await _get_tenant(model.tenant_id, session, user_id)
    model = await repo.update_statut(declaration_id, body.statut)
    await session.commit()

    return TVADeclarationResponse(
        id=model.id,
        tenant_id=model.tenant_id,
        date_debut=model.date_debut,
        date_fin=model.date_fin,
        tva_collectee=model.tva_collectee,
        tva_deductible=model.tva_deductible,
        tva_nette=model.tva_nette,
        lignes=model.lignes,
        statut=model.statut,
        created_at=model.created_at,
        deposee_le=model.deposee_le,
        payee_le=model.payee_le,
    )
