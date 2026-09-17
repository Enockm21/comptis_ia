from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import FactureModel


class SQLAlchemyFactureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, data: dict) -> FactureModel:
        obj = FactureModel(
            id=uuid4(),
            tenant_id=data["tenant_id"],
            statut=data.get("statut", "validee"),
            fournisseur=data["fournisseur"],
            date_facture=data["date_facture"],
            numero_facture=data.get("numero_facture", ""),
            montant_ht=data["montant_ht"],
            taux_tva=data.get("taux_tva", Decimal("20")),
            montant_tva=data["montant_tva"],
            montant_ttc=data["montant_ttc"],
            compte_charge=data.get("compte_charge", "606100"),
            journal_code=data.get("journal_code", "HA"),
            notes=data.get("notes", ""),
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(obj)
        await self._session.flush()
        return obj

    async def list_by_tenant(self, tenant_id: UUID) -> list[FactureModel]:
        result = await self._session.execute(
            select(FactureModel)
            .where(FactureModel.tenant_id == tenant_id)
            .order_by(FactureModel.date_facture.desc())
        )
        return list(result.scalars().all())

    async def delete(self, facture_id: UUID, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(FactureModel).where(
                FactureModel.id == facture_id,
                FactureModel.tenant_id == tenant_id,
            )
        )
