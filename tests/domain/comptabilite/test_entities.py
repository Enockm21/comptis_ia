from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture
from comptis.domain.comptabilite.value_objects import StatutEcriture


def test_compte_comptable_auto_generates_uuid():
    compte = CompteComptable(tenant_id=uuid4(), numero="625100", libelle="Voyages", classe=6)
    assert isinstance(compte.id, UUID)


def test_compte_comptable_has_created_at():
    compte = CompteComptable(tenant_id=uuid4(), numero="625100", libelle="Voyages", classe=6)
    assert isinstance(compte.created_at, datetime)


def test_ecriture_defaults_to_a_categoriser_with_no_compte():
    ecriture = Ecriture(
        tenant_id=uuid4(),
        transaction_id="t1",
        facture_id="f1",
        montant=Decimal("7.10"),
        date=date(2026, 7, 31),
    )
    assert ecriture.compte_id is None
    assert ecriture.statut == StatutEcriture.A_CATEGORISER


def test_ecriture_can_be_created_with_explicit_compte():
    compte_id = uuid4()
    ecriture = Ecriture(
        tenant_id=uuid4(),
        transaction_id="t1",
        facture_id="f1",
        montant=Decimal("7.10"),
        date=date(2026, 7, 31),
        compte_id=compte_id,
        statut=StatutEcriture.CATEGORISEE,
    )
    assert ecriture.compte_id == compte_id
    assert ecriture.statut == StatutEcriture.CATEGORISEE


def test_two_ecritures_have_different_ids():
    a = Ecriture(tenant_id=uuid4(), transaction_id="t1", facture_id="f1", montant=Decimal("1"), date=date(2026, 1, 1))
    b = Ecriture(tenant_id=uuid4(), transaction_id="t2", facture_id="f2", montant=Decimal("1"), date=date(2026, 1, 1))
    assert a.id != b.id


def test_statut_ecriture_is_string():
    assert isinstance(StatutEcriture.A_CATEGORISER, str)
    assert StatutEcriture.A_CATEGORISER == "a_categoriser"
    assert StatutEcriture.CATEGORISEE == "categorisee"
    assert StatutEcriture.VALIDEE == "validee"
