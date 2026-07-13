from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.domain.rapprochement.entities import (
    Conflict,
    Facture,
    Match,
    ReconciliationPattern,
    ReconciliationReport,
    Transaction,
)


def test_transaction_defaults():
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 1), libelle="FACTURE ABC")
    assert t.facture_id is None


def test_facture_defaults():
    f = Facture(
        id="f1",
        montant=Decimal("100.00"),
        date=date(2026, 1, 1),
        fournisseur="ABC SARL",
        statut_rapprochement="non_rapprochee",
    )
    assert f.transaction_id is None


def test_match_fields():
    m = Match(
        facture_id="f1",
        transaction_id="t1",
        confidence=0.92,
        ecart_montant=Decimal("0.00"),
        statut="confirme",
    )
    assert m.confidence == 0.92
    assert m.statut == "confirme"


def test_conflict_facture_can_be_none():
    t = Transaction(id="t1", montant=Decimal("50.00"), date=date(2026, 1, 5), libelle="VIREMENT")
    c = Conflict(transaction=t, facture=None, raison="confidence_insuffisante", composite_score=0.3)
    assert c.facture is None


def test_reconciliation_pattern_default_id():
    p = ReconciliationPattern(
        tenant_id=uuid4(),
        libelle_pattern="FACTURE ABC",
        fournisseur="ABC SARL",
        montant_approx=Decimal("100.00"),
        occurrence_count=1,
        last_seen_at=datetime(2026, 1, 1),
    )
    assert p.id is not None


def test_reconciliation_report():
    tenant_id = uuid4()
    r = ReconciliationReport(
        tenant_id=tenant_id,
        date_debut=date(2026, 1, 1),
        date_fin=date(2026, 1, 7),
        total_transactions=3,
        total_rapprochees=2,
        total_non_rapprochees=1,
        total_ecarts=0,
        matches=[],
        unmatched=[],
    )
    assert r.total_transactions == 3
