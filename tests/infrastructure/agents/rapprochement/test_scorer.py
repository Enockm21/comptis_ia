from datetime import date
from decimal import Decimal

import pytest

from comptis.domain.rapprochement.entities import Facture, Transaction
from comptis.infrastructure.agents.rapprochement.scorer import (
    compute_composite_score,
    prefilter_candidates,
)


def _transaction(libelle: str = "FACTURE ABC", montant: str = "100.00", days_offset: int = 0) -> Transaction:
    return Transaction(
        id="t1",
        montant=Decimal(montant),
        date=date(2026, 1, 15).replace(day=15 + days_offset) if days_offset == 0 else date(2026, 1, 15),
        libelle=libelle,
    )


def _facture(fournisseur: str = "ABC SARL", montant: str = "100.00", days_offset: int = 0) -> Facture:
    base = date(2026, 1, 15)
    from datetime import timedelta
    return Facture(
        id="f1",
        montant=Decimal(montant),
        date=base + timedelta(days=days_offset),
        fournisseur=fournisseur,
        statut_rapprochement="non_rapprochee",
    )


def test_perfect_match_near_1():
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="FACTURE ABC SARL")
    f = _facture(fournisseur="ABC SARL", montant="100.00", days_offset=0)
    score = compute_composite_score(t, f)
    assert score > 0.85


def test_amount_8_percent_off_reduces_score():
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC")
    f = _facture(montant="108.00")
    score = compute_composite_score(t, f)
    # amount_score ≈ 1 - 0.08 = 0.92, but overall lower than perfect
    assert score < 1.0


def test_date_25_days_off_reduces_score():
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 1), libelle="ABC")
    f = _facture(days_offset=25)
    score = compute_composite_score(t, f)
    # date_score = 1 - 25/30 ≈ 0.167
    assert score < 0.8


def test_very_different_libelle_low_text_score():
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="VIREMENT DIVERS")
    f = _facture(fournisseur="ENTREPRISE DUPONT")
    score = compute_composite_score(t, f)
    assert score < 0.75


def test_prefilter_excludes_out_of_range_amount():
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="X")
    too_high = _facture(montant="200.00")  # 100% off
    ok = _facture(montant="100.00")
    result = prefilter_candidates(t, [too_high, ok])
    assert len(result) == 1
    assert result[0].montant == Decimal("100.00")


def test_prefilter_excludes_already_reconciled():
    from comptis.domain.rapprochement.entities import Facture as F
    from decimal import Decimal
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="X")
    already = F(id="f2", montant=Decimal("100.00"), date=date(2026, 1, 15),
                fournisseur="Y", statut_rapprochement="rapprochee")
    ok = _facture()
    result = prefilter_candidates(t, [already, ok])
    assert len(result) == 1
