import pytest
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture


class FakeCompteComptableRepository:
    def __init__(self) -> None:
        self.saved: list[CompteComptable] = []

    async def save(self, compte: CompteComptable) -> None:
        self.saved.append(compte)

    async def list_by_tenant(self, tenant_id: UUID) -> list[CompteComptable]:
        return [c for c in self.saved if c.tenant_id == tenant_id]


class FakeEcritureRepository:
    def __init__(self) -> None:
        self.saved: list[Ecriture] = []

    async def save(self, ecriture: Ecriture) -> None:
        self.saved.append(ecriture)


class FakePlanComptableSource:
    def __init__(self, comptes: list[tuple[str, str]]) -> None:
        self._comptes = comptes

    async def list_comptes(self) -> list[tuple[str, str]]:
        return self._comptes


@pytest.fixture
def compte_repo() -> FakeCompteComptableRepository:
    return FakeCompteComptableRepository()


@pytest.fixture
def ecriture_repo() -> FakeEcritureRepository:
    return FakeEcritureRepository()
