from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import FactureClientModel, LigneFactureClientModel


class SQLAlchemyFactureClientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_numero(self, tenant_id: UUID, type_: str) -> str:
        prefix = "F" if type_ == "facture" else "D"
        year = datetime.now().year
        result = await self._session.execute(
            select(FactureClientModel)
            .where(
                FactureClientModel.tenant_id == tenant_id,
                FactureClientModel.type == type_,
                FactureClientModel.numero.like(f"{prefix}{year}%"),
            )
            .order_by(FactureClientModel.numero.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        if last is None:
            seq = 1
        else:
            try:
                seq = int(last.numero[len(f"{prefix}{year}"):]) + 1
            except ValueError:
                seq = 1
        return f"{prefix}{year}{seq:04d}"

    async def create(
        self,
        tenant_id: UUID,
        data: dict,
        lignes: list[dict],
    ) -> FactureClientModel:
        obj = FactureClientModel(
            id=uuid4(),
            tenant_id=tenant_id,
            type=data.get("type", "facture"),
            statut="brouillon",
            numero=data["numero"],
            date_emission=data["date_emission"],
            date_echeance=data.get("date_echeance"),
            client_nom=data["client_nom"],
            client_adresse=data.get("client_adresse", ""),
            client_email=data.get("client_email", ""),
            notes=data.get("notes", ""),
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(obj)
        await self._session.flush()

        for i, l in enumerate(lignes):
            self._session.add(LigneFactureClientModel(
                id=uuid4(),
                facture_id=obj.id,
                tenant_id=tenant_id,
                description=l["description"],
                quantite=Decimal(str(l.get("quantite", "1"))),
                prix_unitaire=Decimal(str(l["prix_unitaire"])),
                taux_tva=Decimal(str(l.get("taux_tva", "20"))),
                ordre=i,
            ))
        await self._session.flush()
        return obj

    async def list_by_tenant(self, tenant_id: UUID) -> list[FactureClientModel]:
        result = await self._session.execute(
            select(FactureClientModel)
            .where(FactureClientModel.tenant_id == tenant_id)
            .order_by(FactureClientModel.date_emission.desc())
        )
        return list(result.scalars().all())

    async def get(self, facture_id: UUID, tenant_id: UUID) -> FactureClientModel | None:
        result = await self._session.execute(
            select(FactureClientModel).where(
                FactureClientModel.id == facture_id,
                FactureClientModel.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_lignes(self, facture_id: UUID) -> list[LigneFactureClientModel]:
        result = await self._session.execute(
            select(LigneFactureClientModel)
            .where(LigneFactureClientModel.facture_id == facture_id)
            .order_by(LigneFactureClientModel.ordre)
        )
        return list(result.scalars().all())

    async def update_statut(self, facture_id: UUID, tenant_id: UUID, statut: str) -> None:
        f = await self.get(facture_id, tenant_id)
        if f:
            f.statut = statut

    async def delete(self, facture_id: UUID, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(LigneFactureClientModel).where(
                LigneFactureClientModel.facture_id == facture_id
            )
        )
        await self._session.execute(
            delete(FactureClientModel).where(
                FactureClientModel.id == facture_id,
                FactureClientModel.tenant_id == tenant_id,
            )
        )
