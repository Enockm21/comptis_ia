from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture

from .ports import CompteComptableRepository, EcritureRepository, PlanComptableSource


@dataclass
class ImporterPlanComptable:
    compte_repo: CompteComptableRepository
    source: PlanComptableSource

    async def execute(self, tenant_id: UUID) -> list[CompteComptable]:
        comptes = []
        for numero, libelle in await self.source.list_comptes():
            classe = int(numero[0]) if numero[:1].isdigit() else 0
            compte = CompteComptable(
                tenant_id=tenant_id, numero=numero, libelle=libelle, classe=classe,
            )
            await self.compte_repo.save(compte)
            comptes.append(compte)
        return comptes


@dataclass
class CreerEcritureDepuisMatch:
    ecriture_repo: EcritureRepository

    async def execute(
        self,
        tenant_id: UUID,
        transaction_id: str,
        facture_id: str,
        montant: Decimal,
        date_: date,
    ) -> Ecriture:
        ecriture = Ecriture(
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            facture_id=facture_id,
            montant=montant,
            date=date_,
        )
        await self.ecriture_repo.save(ecriture)
        return ecriture
