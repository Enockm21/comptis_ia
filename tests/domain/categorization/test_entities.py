from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from comptis.domain.categorization.entities import (
    CategorizationDecision,
    CategorizationPattern,
    CategorizationSuggestion,
    CompteComptable,
    EcritureACategoriser,
)
from comptis.domain.categorization.value_objects import CategorizationSource, CategorizationStatut


def test_compte_comptable_fields():
    compte = CompteComptable(code="626100", libelle="Frais de télécommunications", classe=6)
    assert compte.code == "626100"
    assert compte.classe == 6


def test_ecriture_a_categoriser_fields():
    e = EcritureACategoriser(
        id=uuid4(), libelle="BRETAGNE TELECOM", montant=Decimal("120.50"),
        tiers="Bretagne Telecom", date=date(2024, 1, 19),
    )
    assert e.montant == Decimal("120.50")


def test_categorization_pattern_auto_generates_uuid():
    p = CategorizationPattern(
        tenant_id=uuid4(), libelle_pattern="BRETAGNE TELECOM", fournisseur="Bretagne Telecom",
        compte_code="626100", occurrence_count=1, last_seen_at=datetime.now(tz=timezone.utc),
    )
    assert isinstance(p.id, UUID)


def test_categorization_suggestion_carries_evidence():
    s = CategorizationSuggestion(
        compte_code="626100", confidence=0.92, source=CategorizationSource.PATTERN,
        evidence=["BRETAGNE TELECOM -> 626100 (vu 5 fois)"],
    )
    assert s.evidence == ["BRETAGNE TELECOM -> 626100 (vu 5 fois)"]
    assert s.source == CategorizationSource.PATTERN


def test_categorization_decision_requires_tenant_id():
    d = CategorizationDecision(
        id=uuid4(), tenant_id=uuid4(), ecriture_id=uuid4(), compte_code="626100",
        statut=CategorizationStatut.AUTO_VALIDATED, confidence=0.92, validated_by=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    assert d.validated_by is None
    assert d.statut == CategorizationStatut.AUTO_VALIDATED
