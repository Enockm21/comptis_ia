from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.models import EcritureModel, FactureClientModel
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/alertes", tags=["alertes"])


class Alerte(BaseModel):
    type: str          # "ecritures" | "facture_impayee" | "tva_deadline"
    titre: str
    detail: str
    priorite: str      # "haute" | "normale"
    action_url: str


@router.get("", response_model=list[Alerte])
async def get_alertes(
    tenant_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[Alerte]:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        return []
    await set_tenant_context(
        session, organization_id=tenant.organization_id,
        tenant_id=tenant_id, user_id=user_id,
    )

    alertes: list[Alerte] = []
    today = date.today()

    # ── Écritures à catégoriser ──────────────────────────────────────────────
    count_row = await session.execute(
        select(func.count()).select_from(EcritureModel).where(
            EcritureModel.tenant_id == tenant_id,
            EcritureModel.statut == "a_categoriser",
        )
    )
    n_ecriture = count_row.scalar_one()
    if n_ecriture > 0:
        alertes.append(Alerte(
            type="ecritures",
            titre=f"{n_ecriture} écriture(s) à catégoriser",
            detail="Des transactions importées attendent une catégorisation comptable.",
            priorite="haute" if n_ecriture >= 10 else "normale",
            action_url="/categorisation",
        ))

    # ── Factures client impayées + en retard ─────────────────────────────────
    overdue_result = await session.execute(
        select(func.count()).select_from(FactureClientModel).where(
            FactureClientModel.tenant_id == tenant_id,
            FactureClientModel.statut == "envoyee",
            FactureClientModel.date_echeance < today,
        )
    )
    n_overdue = overdue_result.scalar_one() or 0
    if n_overdue > 0:
        alertes.append(Alerte(
            type="facture_impayee",
            titre=f"{n_overdue} facture(s) en retard de paiement",
            detail="Des factures envoyées ont dépassé leur date d'échéance.",
            priorite="haute",
            action_url="/facturation",
        ))

    # Factures qui arrivent à échéance dans 7 jours
    soon_result = await session.execute(
        select(func.count()).select_from(FactureClientModel).where(
            FactureClientModel.tenant_id == tenant_id,
            FactureClientModel.statut == "envoyee",
            FactureClientModel.date_echeance >= today,
            FactureClientModel.date_echeance <= today + timedelta(days=7),
        )
    )
    n_soon = soon_result.scalar_one()
    if n_soon > 0:
        alertes.append(Alerte(
            type="facture_echeance",
            titre=f"{n_soon} facture(s) arrivent à échéance sous 7 jours",
            detail="Vérifiez que le paiement a bien été reçu.",
            priorite="normale",
            action_url="/facturation",
        ))

    # ── Deadline TVA (CA3 trimestrielle) ─────────────────────────────────────
    month = today.month
    quarter_deadlines = {4: date(today.year, 4, 30), 7: date(today.year, 7, 31),
                         10: date(today.year, 10, 31), 1: date(today.year, 1, 31)}
    for m, dl in quarter_deadlines.items():
        if dl >= today and (dl - today).days <= 14:
            alertes.append(Alerte(
                type="tva_deadline",
                titre="Déclaration TVA CA3 à soumettre",
                detail=f"La déclaration CA3 est à déposer avant le {dl.strftime('%d/%m/%Y')}.",
                priorite="haute",
                action_url="/tva",
            ))
            break

    return alertes
