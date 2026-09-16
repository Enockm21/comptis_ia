from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture, LigneGrandLivre

from .models import EcritureModel, GrandLivreModel, PlanComptableModel


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


class SQLAlchemyGrandLivreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_many(self, lignes: list[LigneGrandLivre]) -> int:
        if not lignes:
            return 0
        rows = [
            dict(
                id=lg.id, tenant_id=lg.tenant_id,
                journal_code=lg.journal_code, journal_lib=lg.journal_lib,
                ecriture_num=lg.ecriture_num, ecriture_date=lg.ecriture_date,
                compte_num=lg.compte_num, compte_lib=lg.compte_lib,
                comp_aux_num=lg.comp_aux_num, comp_aux_lib=lg.comp_aux_lib,
                piece_ref=lg.piece_ref, piece_date=lg.piece_date,
                ecriture_lib=lg.ecriture_lib,
                debit=lg.debit, credit=lg.credit,
                ecriture_let=lg.ecriture_let, date_let=lg.date_let,
                valid_date=lg.valid_date,
                montantdevise=lg.montantdevise, idevise=lg.idevise,
                created_at=lg.created_at,
            )
            for lg in lignes
        ]
        await self._session.execute(insert(GrandLivreModel).values(rows).on_conflict_do_nothing())
        await self._session.flush()
        return len(lignes)

    async def list_by_tenant(
        self, tenant_id: UUID, date_debut: date | None, date_fin: date | None
    ) -> list[LigneGrandLivre]:
        stmt = (
            select(GrandLivreModel)
            .where(GrandLivreModel.tenant_id == tenant_id)
            .order_by(GrandLivreModel.ecriture_date, GrandLivreModel.journal_code, GrandLivreModel.ecriture_num)
        )
        if date_debut:
            stmt = stmt.where(GrandLivreModel.ecriture_date >= date_debut)
        if date_fin:
            stmt = stmt.where(GrandLivreModel.ecriture_date <= date_fin)
        result = await self._session.execute(stmt)
        return [_gl_to_domain(m) for m in result.scalars().all()]

    async def delete_by_tenant(self, tenant_id: UUID) -> None:
        await self._session.execute(
            delete(GrandLivreModel).where(GrandLivreModel.tenant_id == tenant_id)
        )
        await self._session.flush()


def _gl_to_domain(m: GrandLivreModel) -> LigneGrandLivre:
    from decimal import Decimal
    return LigneGrandLivre(
        id=m.id, tenant_id=m.tenant_id,
        journal_code=m.journal_code, journal_lib=m.journal_lib,
        ecriture_num=m.ecriture_num, ecriture_date=m.ecriture_date,
        compte_num=m.compte_num, compte_lib=m.compte_lib,
        comp_aux_num=m.comp_aux_num or "", comp_aux_lib=m.comp_aux_lib or "",
        piece_ref=m.piece_ref, piece_date=m.piece_date,
        ecriture_lib=m.ecriture_lib,
        debit=Decimal(str(m.debit)), credit=Decimal(str(m.credit)),
        ecriture_let=m.ecriture_let or "", date_let=m.date_let,
        valid_date=m.valid_date,
        montantdevise=Decimal(str(m.montantdevise)), idevise=m.idevise or "",
        created_at=m.created_at,
    )
