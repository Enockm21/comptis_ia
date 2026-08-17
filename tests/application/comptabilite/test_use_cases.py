import pytest
from datetime import date
from decimal import Decimal
from uuid import uuid4

from comptis.application.comptabilite.use_cases import (
    CreerEcritureDepuisMatch,
    ImporterPlanComptable,
)
from comptis.domain.comptabilite.value_objects import StatutEcriture

from .conftest import FakePlanComptableSource

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_importer_plan_comptable_saves_each_compte(compte_repo):
    tenant_id = uuid4()
    source = FakePlanComptableSource([("625100", "Voyages et déplacements"), ("606400", "Fournitures")])
    use_case = ImporterPlanComptable(compte_repo=compte_repo, source=source)

    comptes = await use_case.execute(tenant_id)

    assert len(comptes) == 2
    assert len(compte_repo.saved) == 2
    numeros = {c.numero for c in compte_repo.saved}
    assert numeros == {"625100", "606400"}


async def test_importer_plan_comptable_derives_classe_from_numero():
    tenant_id = uuid4()
    from tests.application.comptabilite.conftest import FakeCompteComptableRepository

    repo = FakeCompteComptableRepository()
    source = FakePlanComptableSource([("625100", "Voyages")])
    use_case = ImporterPlanComptable(compte_repo=repo, source=source)

    comptes = await use_case.execute(tenant_id)

    assert comptes[0].classe == 6


async def test_importer_plan_comptable_sets_tenant_id_on_every_compte(compte_repo):
    tenant_id = uuid4()
    source = FakePlanComptableSource([("625100", "Voyages"), ("606400", "Fournitures")])
    use_case = ImporterPlanComptable(compte_repo=compte_repo, source=source)

    comptes = await use_case.execute(tenant_id)

    assert all(c.tenant_id == tenant_id for c in comptes)


async def test_creer_ecriture_depuis_match_saves_and_returns(ecriture_repo):
    tenant_id = uuid4()
    use_case = CreerEcritureDepuisMatch(ecriture_repo=ecriture_repo)

    ecriture = await use_case.execute(
        tenant_id=tenant_id,
        transaction_id="t1",
        facture_id="f1",
        montant=Decimal("7.10"),
        date_=date(2026, 7, 31),
    )

    assert ecriture.tenant_id == tenant_id
    assert ecriture.transaction_id == "t1"
    assert ecriture.facture_id == "f1"
    assert ecriture.montant == Decimal("7.10")
    assert ecriture.compte_id is None
    assert ecriture.statut == StatutEcriture.A_CATEGORISER
    assert ecriture_repo.saved == [ecriture]
