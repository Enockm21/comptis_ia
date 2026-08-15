from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.application.categorization.use_cases import CategorizeEcriture, ValidateCategorization
from comptis.domain.categorization.entities import (
    CategorizationDecision,
    CategorizationPattern,
    CategorizationSuggestion,
    EcritureACategoriser,
)
from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError
from comptis.domain.categorization.value_objects import CategorizationSource, CategorizationStatut


class _FakePatternRepo:
    def __init__(self, existing: CategorizationPattern | None = None) -> None:
        self._existing = existing
        self.upserted: list[CategorizationPattern] = []

    async def find_by_libelle(self, tenant_id, libelle_pattern):
        return self._existing

    async def upsert(self, pattern):
        self.upserted.append(pattern)
        return pattern


class _FakeRetriever:
    def __init__(self, results: list[CategorizationSuggestion]) -> None:
        self._results = results

    async def search(self, query, top_k=5):
        return self._results


class _FakeDecisionRepo:
    def __init__(self) -> None:
        self.saved: list[CategorizationDecision] = []

    async def save(self, decision):
        self.saved.append(decision)

    async def get_by_ecriture(self, ecriture_id):
        for d in reversed(self.saved):
            if d.ecriture_id == ecriture_id:
                return d
        return None


def _ecriture(libelle="BRETAGNE TELECOM", tiers="Bretagne Telecom") -> EcritureACategoriser:
    return EcritureACategoriser(
        id=uuid4(), libelle=libelle, montant=Decimal("120.50"), tiers=tiers, date=date(2024, 1, 19),
    )


async def test_trusted_pattern_wins_over_rag():
    pattern = CategorizationPattern(
        tenant_id=uuid4(), libelle_pattern="BRETAGNE TELECOM", fournisseur="Bretagne Telecom",
        compte_code="626100", occurrence_count=5, last_seen_at=datetime.now(tz=timezone.utc),
    )
    uc = CategorizeEcriture(
        pattern_repo=_FakePatternRepo(existing=pattern),
        account_retriever=_FakeRetriever([]),
        decision_repo=_FakeDecisionRepo(),
    )
    decision = await uc.execute(tenant_id=pattern.tenant_id, ecriture=_ecriture())
    assert decision.compte_code == "626100"
    assert decision.statut == CategorizationStatut.AUTO_VALIDATED


async def test_pattern_below_occurrence_threshold_falls_back_to_rag():
    pattern = CategorizationPattern(
        tenant_id=uuid4(), libelle_pattern="BRETAGNE TELECOM", fournisseur="Bretagne Telecom",
        compte_code="626100", occurrence_count=1, last_seen_at=datetime.now(tz=timezone.utc),
    )
    rag_result = CategorizationSuggestion(
        compte_code="613500", confidence=0.9, source=CategorizationSource.RAG,
    )
    uc = CategorizeEcriture(
        pattern_repo=_FakePatternRepo(existing=pattern),
        account_retriever=_FakeRetriever([rag_result]),
        decision_repo=_FakeDecisionRepo(),
        min_occurrence_threshold=3,
    )
    decision = await uc.execute(tenant_id=pattern.tenant_id, ecriture=_ecriture())
    assert decision.compte_code == "613500"


async def test_high_confidence_rag_auto_validates():
    rag_result = CategorizationSuggestion(
        compte_code="626100", confidence=0.9, source=CategorizationSource.RAG,
    )
    uc = CategorizeEcriture(
        pattern_repo=_FakePatternRepo(existing=None),
        account_retriever=_FakeRetriever([rag_result]),
        decision_repo=_FakeDecisionRepo(),
    )
    decision = await uc.execute(tenant_id=uuid4(), ecriture=_ecriture())
    assert decision.statut == CategorizationStatut.AUTO_VALIDATED
    assert decision.confidence == 0.9


async def test_low_confidence_rag_needs_review():
    rag_result = CategorizationSuggestion(
        compte_code="626100", confidence=0.4, source=CategorizationSource.RAG,
    )
    uc = CategorizeEcriture(
        pattern_repo=_FakePatternRepo(existing=None),
        account_retriever=_FakeRetriever([rag_result]),
        decision_repo=_FakeDecisionRepo(),
    )
    decision = await uc.execute(tenant_id=uuid4(), ecriture=_ecriture())
    assert decision.statut == CategorizationStatut.PENDING_REVIEW


async def test_no_candidates_needs_review_with_zero_confidence():
    uc = CategorizeEcriture(
        pattern_repo=_FakePatternRepo(existing=None),
        account_retriever=_FakeRetriever([]),
        decision_repo=_FakeDecisionRepo(),
    )
    decision = await uc.execute(tenant_id=uuid4(), ecriture=_ecriture())
    assert decision.statut == CategorizationStatut.PENDING_REVIEW
    assert decision.confidence == 0.0


async def test_decision_is_persisted():
    rag_result = CategorizationSuggestion(
        compte_code="626100", confidence=0.9, source=CategorizationSource.RAG,
    )
    decision_repo = _FakeDecisionRepo()
    uc = CategorizeEcriture(
        pattern_repo=_FakePatternRepo(existing=None),
        account_retriever=_FakeRetriever([rag_result]),
        decision_repo=decision_repo,
    )
    ecriture = _ecriture()
    await uc.execute(tenant_id=uuid4(), ecriture=ecriture)
    assert len(decision_repo.saved) == 1
    assert decision_repo.saved[0].ecriture_id == ecriture.id


async def test_validate_marks_human_validated_and_learns_pattern():
    pattern_repo = _FakePatternRepo(existing=None)
    decision_repo = _FakeDecisionRepo()
    tenant_id = uuid4()
    ecriture = _ecriture()

    categorize = CategorizeEcriture(
        pattern_repo=pattern_repo,
        account_retriever=_FakeRetriever([
            CategorizationSuggestion(compte_code="626100", confidence=0.4, source=CategorizationSource.RAG)
        ]),
        decision_repo=decision_repo,
    )
    pending = await categorize.execute(tenant_id=tenant_id, ecriture=ecriture)
    assert pending.statut == CategorizationStatut.PENDING_REVIEW

    validator = ValidateCategorization(pattern_repo=pattern_repo, decision_repo=decision_repo)
    validated_by = uuid4()
    result = await validator.execute(
        tenant_id=tenant_id, ecriture=ecriture, compte_code="613500", validated_by=validated_by,
    )

    assert result.statut == CategorizationStatut.HUMAN_VALIDATED
    assert result.compte_code == "613500"
    assert result.validated_by == validated_by
    assert result.confidence == 1.0
    assert len(pattern_repo.upserted) == 1
    assert pattern_repo.upserted[0].compte_code == "613500"
    assert pattern_repo.upserted[0].fournisseur == ecriture.tiers


async def test_auto_validated_decision_does_not_upsert_pattern():
    pattern_repo = _FakePatternRepo(existing=None)
    decision_repo = _FakeDecisionRepo()
    tenant_id = uuid4()
    ecriture = _ecriture()

    categorize = CategorizeEcriture(
        pattern_repo=pattern_repo,
        account_retriever=_FakeRetriever([
            CategorizationSuggestion(compte_code="626100", confidence=0.9, source=CategorizationSource.RAG)
        ]),
        decision_repo=decision_repo,
    )
    await categorize.execute(tenant_id=tenant_id, ecriture=ecriture)

    assert pattern_repo.upserted == []


async def test_validate_raises_when_no_prior_decision():
    validator = ValidateCategorization(
        pattern_repo=_FakePatternRepo(existing=None), decision_repo=_FakeDecisionRepo(),
    )
    with pytest.raises(CategorizationDecisionNotFoundError):
        await validator.execute(
            tenant_id=uuid4(), ecriture=_ecriture(), compte_code="626100", validated_by=uuid4(),
        )


async def test_validate_raises_when_existing_decision_belongs_to_different_tenant():
    pattern_repo = _FakePatternRepo(existing=None)
    decision_repo = _FakeDecisionRepo()
    owning_tenant_id = uuid4()
    other_tenant_id = uuid4()
    ecriture = _ecriture()

    categorize = CategorizeEcriture(
        pattern_repo=pattern_repo,
        account_retriever=_FakeRetriever([
            CategorizationSuggestion(compte_code="626100", confidence=0.4, source=CategorizationSource.RAG)
        ]),
        decision_repo=decision_repo,
    )
    await categorize.execute(tenant_id=owning_tenant_id, ecriture=ecriture)

    validator = ValidateCategorization(pattern_repo=pattern_repo, decision_repo=decision_repo)
    with pytest.raises(CategorizationDecisionNotFoundError):
        await validator.execute(
            tenant_id=other_tenant_id, ecriture=ecriture, compte_code="613500", validated_by=uuid4(),
        )

    assert pattern_repo.upserted == []
