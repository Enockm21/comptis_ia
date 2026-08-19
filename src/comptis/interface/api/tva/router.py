from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Body
from pydantic import BaseModel

from comptis.application.tva.use_cases import ComputeTVA
from comptis.infrastructure.pdf.ca3_generator import CA3Data, generate_ca3
from comptis.infrastructure.pdf.ca3_overlay import CA3OverlayData, fill_ca3
from comptis.domain.tva.entities import TVADeclaration
from comptis.infrastructure.db.models import CA3DeclarationModel
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
from sqlalchemy import select


class CA3Schema(BaseModel):
    tenant_id: uuid.UUID
    periode_debut: date
    periode_fin: date
    raison_sociale: str = ""
    adresse: str = ""
    code_postal_ville: str = ""
    siret: str = ""
    numero_tva: str = ""
    a1_ventes: Decimal = Decimal(0)
    l08_base: Decimal = Decimal(0)
    l08_taxe: Decimal = Decimal(0)
    l09_base: Decimal = Decimal(0)
    l09_taxe: Decimal = Decimal(0)
    l9b_base: Decimal = Decimal(0)
    l9b_taxe: Decimal = Decimal(0)
    l16_brute: Decimal = Decimal(0)
    l19_immos: Decimal = Decimal(0)
    l20_autres: Decimal = Decimal(0)
    l22_report: Decimal = Decimal(0)
    l23_total_ded: Decimal = Decimal(0)
    tva_due: Decimal = Decimal(0)
    credit_tva: Decimal = Decimal(0)

    class Config:
        from_attributes = True


class CA3SavedSchema(CA3Schema):
    id: uuid.UUID

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


@router.get("/export-ca3")
async def export_ca3(
    tenant_id: uuid.UUID,
    date_debut: date,
    date_fin: date,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Génère le formulaire CA3 en PDF pour la période donnée."""
    tenant = await _get_tenant(tenant_id, session, user_id)
    mcp_client = await build_mcp_client_for_org(tenant.organization_id, session)
    summary = await ComputeTVA(mcp_client).execute(tenant_id, date_debut, date_fin)

    # Récupère base HT par taux depuis les lignes déductibles
    base_by_taux: dict[str, Decimal] = {str(l.taux): l.base_ht for l in summary.lignes_deductible}
    tva_by_taux: dict[str, Decimal] = {str(l.taux): l.montant_tva for l in summary.lignes_deductible}

    # Base HT collectée par taux
    cbase_by_taux: dict[str, Decimal] = {str(l.taux): l.base_ht for l in summary.lignes_collectee}
    ctva_by_taux: dict[str, Decimal] = {str(l.taux): l.montant_tva for l in summary.lignes_collectee}

    # Récupère les infos société depuis le tenant (champs étendus optionnels)
    org_name = getattr(tenant, "name", None) or getattr(tenant, "nom", None) or "ENTREPRISE"
    adresse = getattr(tenant, "adresse", "") or ""
    cp_ville = getattr(tenant, "code_postal_ville", "") or ""
    siret = getattr(tenant, "siret", "") or "_ _ _ _ _ _ _ _ _ _ _ _ _ _ _"
    tva_intra = getattr(tenant, "numero_tva", "") or "FR _ _ _ _ _ _ _ _ _ _ _"

    data = CA3Data(
        raison_sociale=org_name,
        adresse=adresse,
        code_postal_ville=cp_ville,
        siret=siret,
        tva_intracomm=tva_intra,
        periode_debut=date_debut,
        periode_fin=date_fin,
        # TVA brute (collectée = ventes)
        b08_base_20=cbase_by_taux.get("20.00", Decimal("0")),
        b08_taxe_20=ctva_by_taux.get("20.00", Decimal("0")),
        b9b_base_10=cbase_by_taux.get("10.00", Decimal("0")),
        b9b_taxe_10=ctva_by_taux.get("10.00", Decimal("0")),
        b09_base_55=cbase_by_taux.get("5.50", Decimal("0")),
        b09_taxe_55=ctva_by_taux.get("5.50", Decimal("0")),
        # TVA déductible (achats)
        ded_20_autres=summary.tva_deductible,
    )

    import logging
    try:
        pdf_bytes = generate_ca3(data)
    except Exception as exc:
        logging.exception("ca3 generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = f"CA3_{date_debut.strftime('%Y-%m')}_{org_name.replace(' ', '_')}.pdf"
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


# ── CA3 editor endpoints ────────────────────────────────────────────────────


@router.get("/ca3-compute", response_model=CA3Schema)
async def ca3_compute(
    tenant_id: uuid.UUID,
    date_debut: date,
    date_fin: date,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> CA3Schema:
    """Compute TVA for period and return CA3 form values (pre-fill)."""
    tenant = await _get_tenant(tenant_id, session, user_id)
    mcp_client = await build_mcp_client_for_org(tenant.organization_id, session)
    summary = await ComputeTVA(mcp_client).execute(tenant_id, date_debut, date_fin)

    cbase = {str(l.taux): l.base_ht for l in summary.lignes_collectee}
    ctva = {str(l.taux): l.montant_tva for l in summary.lignes_collectee}

    l08_base = cbase.get("20.00", Decimal(0))
    l08_taxe = ctva.get("20.00", Decimal(0))
    l9b_base = cbase.get("10.00", Decimal(0))
    l9b_taxe = ctva.get("10.00", Decimal(0))
    l09_base = cbase.get("5.50", Decimal(0))
    l09_taxe = ctva.get("5.50", Decimal(0))
    l16_brute = l08_taxe + l9b_taxe + l09_taxe
    l20_autres = summary.tva_deductible
    l23_total_ded = l20_autres
    a1_ventes = sum(cbase.values(), Decimal(0))

    tva_due = Decimal(0)
    credit_tva = Decimal(0)
    if l16_brute >= l23_total_ded:
        tva_due = l16_brute - l23_total_ded
    else:
        credit_tva = l23_total_ded - l16_brute

    return CA3Schema(
        tenant_id=tenant_id,
        periode_debut=date_debut,
        periode_fin=date_fin,
        raison_sociale=getattr(tenant, "name", "") or "",
        adresse=getattr(tenant, "adresse", "") or "",
        code_postal_ville=getattr(tenant, "code_postal_ville", "") or "",
        siret=getattr(tenant, "siret", "") or "",
        numero_tva=getattr(tenant, "numero_tva", "") or "",
        a1_ventes=a1_ventes,
        l08_base=l08_base,
        l08_taxe=l08_taxe,
        l09_base=l09_base,
        l09_taxe=l09_taxe,
        l9b_base=l9b_base,
        l9b_taxe=l9b_taxe,
        l16_brute=l16_brute,
        l19_immos=Decimal(0),
        l20_autres=l20_autres,
        l22_report=Decimal(0),
        l23_total_ded=l23_total_ded,
        tva_due=tva_due,
        credit_tva=credit_tva,
    )


@router.post("/ca3-fill")
async def ca3_fill(
    body: CA3Schema,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Fill the official CA3 PDF template with given values, return PDF bytes."""
    await _get_tenant(body.tenant_id, session, user_id)
    import logging
    try:
        data = CA3OverlayData(
            periode_debut=body.periode_debut,
            periode_fin=body.periode_fin,
            raison_sociale=body.raison_sociale,
            adresse=body.adresse,
            code_postal_ville=body.code_postal_ville,
            siret=body.siret,
            numero_tva=body.numero_tva,
            a1_ventes=body.a1_ventes,
            l08_base=body.l08_base,
            l08_taxe=body.l08_taxe,
            l09_base=body.l09_base,
            l09_taxe=body.l09_taxe,
            l9b_base=body.l9b_base,
            l9b_taxe=body.l9b_taxe,
            l16_brute=body.l16_brute,
            l19_immos=body.l19_immos,
            l20_autres=body.l20_autres,
            l22_report=body.l22_report,
            l23_total_ded=body.l23_total_ded,
            tva_due=body.tva_due,
            credit_tva=body.credit_tva,
        )
        pdf_bytes = fill_ca3(data)
    except Exception as exc:
        logging.exception("ca3 fill failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    month = body.periode_debut.strftime("%Y-%m")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="CA3_{month}.pdf"'},
    )


@router.post("/ca3-declarations", response_model=CA3SavedSchema, status_code=201)
async def ca3_save(
    body: CA3Schema,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> CA3SavedSchema:
    """Save CA3 declaration values to DB (upsert on tenant+periode)."""
    await _get_tenant(body.tenant_id, session, user_id)

    result = await session.execute(
        select(CA3DeclarationModel).where(
            CA3DeclarationModel.tenant_id == body.tenant_id,
            CA3DeclarationModel.periode_debut == body.periode_debut,
        )
    )
    model = result.scalar_one_or_none()
    if model is None:
        model = CA3DeclarationModel(tenant_id=body.tenant_id)
        session.add(model)

    for f in ["periode_debut", "periode_fin", "raison_sociale", "adresse",
              "code_postal_ville", "siret", "numero_tva", "a1_ventes",
              "l08_base", "l08_taxe", "l09_base", "l09_taxe", "l9b_base",
              "l9b_taxe", "l16_brute", "l19_immos", "l20_autres", "l22_report",
              "l23_total_ded", "tva_due", "credit_tva"]:
        setattr(model, f, getattr(body, f))

    await session.flush()
    await session.commit()
    await session.refresh(model)
    return CA3SavedSchema.model_validate(model)


@router.get("/ca3-declarations", response_model=list[CA3SavedSchema])
async def ca3_list(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CA3SavedSchema]:
    await _get_tenant(tenant_id, session, user_id)
    result = await session.execute(
        select(CA3DeclarationModel)
        .where(CA3DeclarationModel.tenant_id == tenant_id)
        .order_by(CA3DeclarationModel.periode_debut.desc())
    )
    return [CA3SavedSchema.model_validate(m) for m in result.scalars().all()]
