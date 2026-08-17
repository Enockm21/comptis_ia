from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture

from .models import PlanComptableModel, EcritureModel


def _ecriture_to_domain(m: EcritureModel) -> Ecriture:
    from comptis.domain.comptabilite.value_objects import StatutEcriture
    return Ecriture(
        id=m.id, tenant_id=m.tenant_id, transaction_id=m.transaction_id,
        facture_id=m.facture_id, montant=m.montant, date=m.date,
        compte_id=m.compte_id, statut=StatutEcriture(m.statut), created_at=m.created_at,
    )


def _compte_to_domain(m: PlanComptableModel) -> CompteComptable:
    return CompteComptable(
        id=m.id, tenant_id=m.tenant_id, numero=m.numero, libelle=m.libelle,
        classe=m.classe, created_at=m.created_at,
    )


class SQLAlchemyCompteComptableRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, compte: CompteComptable) -> None:
        stmt = (
            insert(PlanComptableModel)
            .values(
                id=compte.id, tenant_id=compte.tenant_id, numero=compte.numero,
                libelle=compte.libelle, classe=compte.classe, created_at=compte.created_at,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "numero"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_by_tenant(self, tenant_id: UUID) -> list[CompteComptable]:
        result = await self._session.execute(
            select(PlanComptableModel).where(PlanComptableModel.tenant_id == tenant_id)
        )
        return [_compte_to_domain(m) for m in result.scalars().all()]


class SQLAlchemyEcritureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_tenant(self, tenant_id: UUID, statut: str | None = None) -> list[Ecriture]:
        stmt = select(EcritureModel).where(EcritureModel.tenant_id == tenant_id)
        if statut:
            stmt = stmt.where(EcritureModel.statut == statut)
        stmt = stmt.order_by(EcritureModel.date.desc())
        result = await self._session.execute(stmt)
        return [_ecriture_to_domain(m) for m in result.scalars().all()]

    async def save(self, ecriture: Ecriture) -> None:
        stmt = (
            insert(EcritureModel)
            .values(
                id=ecriture.id, tenant_id=ecriture.tenant_id,
                transaction_id=ecriture.transaction_id, facture_id=ecriture.facture_id,
                montant=ecriture.montant, date=ecriture.date,
                compte_id=ecriture.compte_id, statut=ecriture.statut.value,
                created_at=ecriture.created_at,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "transaction_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
