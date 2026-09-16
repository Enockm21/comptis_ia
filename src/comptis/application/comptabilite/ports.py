from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture, LigneGrandLivre


class CompteComptableRepository(Protocol):
    async def save(self, compte: CompteComptable) -> None: ...
    async def list_by_tenant(self, tenant_id: UUID) -> list[CompteComptable]: ...


class EcritureRepository(Protocol):
    async def save(self, ecriture: Ecriture) -> None: ...


class GrandLivreRepository(Protocol):
    async def save_many(self, lignes: list[LigneGrandLivre]) -> int: ...
    async def list_by_tenant(
        self, tenant_id: UUID, date_debut: date | None, date_fin: date | None
    ) -> list[LigneGrandLivre]: ...
    async def delete_by_tenant(self, tenant_id: UUID) -> None: ...


class PlanComptableSource(Protocol):
    """Source externe d'un plan de comptes à importer (ex: PNiCompta)."""

    async def list_comptes(self) -> list[tuple[str, str]]:  # (numero, libelle)
        ...
