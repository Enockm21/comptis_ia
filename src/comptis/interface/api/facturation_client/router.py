from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.facturation_client.pdf import FacturePDFData, LignePDF, generate_pdf
from comptis.infrastructure.db.factures_client_repository import SQLAlchemyFactureClientRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/facturation-client", tags=["facturation-client"])


async def _set_ctx(tenant_id: uuid.UUID, user_id: uuid.UUID, session: AsyncSession):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    await set_tenant_context(session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id)
    return tenant


# ── Schemas ────────────────────────────────────────────────────────────────────

class LigneIn(BaseModel):
    description: str
    quantite: Decimal = Decimal("1")
    prix_unitaire: Decimal
    taux_tva: Decimal = Decimal("20")


class CreateFactureRequest(BaseModel):
    type: str = "facture"       # "facture" | "devis"
    date_emission: date
    date_echeance: date | None = None
    client_nom: str
    client_adresse: str = ""
    client_email: str = ""
    notes: str = ""
    lignes: list[LigneIn]


class LigneSchema(BaseModel):
    id: uuid.UUID
    description: str
    quantite: Decimal
    prix_unitaire: Decimal
    taux_tva: Decimal
    montant_ht: Decimal
    montant_ttc: Decimal
    ordre: int


class FactureClientSchema(BaseModel):
    id: uuid.UUID
    type: str
    statut: str
    numero: str
    date_emission: date
    date_echeance: date | None
    client_nom: str
    client_adresse: str
    client_email: str
    notes: str
    total_ht: Decimal
    total_tva: Decimal
    total_ttc: Decimal
    lignes: list[LigneSchema] = []
    created_at: datetime


def _ligne_schema(l) -> LigneSchema:
    ht = (l.quantite * l.prix_unitaire).quantize(Decimal("0.01"))
    tva = (ht * l.taux_tva / 100).quantize(Decimal("0.01"))
    return LigneSchema(
        id=l.id, description=l.description,
        quantite=l.quantite, prix_unitaire=l.prix_unitaire,
        taux_tva=l.taux_tva, montant_ht=ht, montant_ttc=ht + tva,
        ordre=l.ordre,
    )


async def _full_schema(f, repo: SQLAlchemyFactureClientRepository) -> FactureClientSchema:
    lignes = await repo.get_lignes(f.id)
    lignes_s = [_ligne_schema(l) for l in lignes]
    total_ht = sum(ls.montant_ht for ls in lignes_s)
    total_ttc = sum(ls.montant_ttc for ls in lignes_s)
    return FactureClientSchema(
        id=f.id, type=f.type, statut=f.statut, numero=f.numero,
        date_emission=f.date_emission, date_echeance=f.date_echeance,
        client_nom=f.client_nom, client_adresse=f.client_adresse,
        client_email=f.client_email, notes=f.notes,
        total_ht=total_ht, total_tva=(total_ttc - total_ht),
        total_ttc=total_ttc, lignes=lignes_s,
        created_at=f.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/factures", response_model=FactureClientSchema)
async def create_facture(
    body: CreateFactureRequest,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> FactureClientSchema:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureClientRepository(session)
    numero = await repo.next_numero(tenant_id, body.type)
    f = await repo.create(
        tenant_id,
        {**body.model_dump(exclude={"lignes"}), "numero": numero},
        [l.model_dump() for l in body.lignes],
    )
    return await _full_schema(f, repo)


@router.get("/factures", response_model=list[FactureClientSchema])
async def list_factures(
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[FactureClientSchema]:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureClientRepository(session)
    rows = await repo.list_by_tenant(tenant_id)
    result = []
    for r in rows:
        result.append(await _full_schema(r, repo))
    return result


@router.patch("/factures/{facture_id}/statut", response_model=FactureClientSchema)
async def update_statut(
    facture_id: uuid.UUID,
    statut: str = Query(...),
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> FactureClientSchema:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureClientRepository(session)
    await repo.update_statut(facture_id, tenant_id, statut)
    f = await repo.get(facture_id, tenant_id)
    if not f:
        raise HTTPException(404, "Facture introuvable")
    return await _full_schema(f, repo)


@router.delete("/factures/{facture_id}", status_code=204)
async def delete_facture(
    facture_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureClientRepository(session)
    await repo.delete(facture_id, tenant_id)


@router.get("/factures/{facture_id}/pdf")
async def export_pdf(
    facture_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    tenant = await _set_ctx(tenant_id, user_id, session)
    repo = SQLAlchemyFactureClientRepository(session)
    f = await repo.get(facture_id, tenant_id)
    if not f:
        raise HTTPException(404, "Facture introuvable")
    lignes = await repo.get_lignes(facture_id)
    data = FacturePDFData(
        type=f.type,
        numero=f.numero,
        date_emission=f.date_emission,
        date_echeance=f.date_echeance,
        emetteur_nom=tenant.name,
        emetteur_adresse=getattr(tenant, "adresse", "") or "",
        emetteur_siret=getattr(tenant, "siret", "") or "",
        emetteur_tva=getattr(tenant, "numero_tva", "") or "",
        client_nom=f.client_nom,
        client_adresse=f.client_adresse,
        client_email=f.client_email,
        lignes=[
            LignePDF(
                description=l.description,
                quantite=l.quantite,
                prix_unitaire=l.prix_unitaire,
                taux_tva=l.taux_tva,
            )
            for l in lignes
        ],
        notes=f.notes,
    )
    pdf_bytes = generate_pdf(data)
    filename = f"{f.numero}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
