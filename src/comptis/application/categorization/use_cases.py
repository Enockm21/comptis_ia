from __future__ import annotations

from uuid import UUID, uuid4

from comptis.application.categorization.ports import (
    AccountRetriever,
    CategorizationDecisionRepository,
    CategorizationPatternRepository,
)
from comptis.domain.categorization.entities import (
    CategorizationDecision,
    CategorizationSuggestion,
    EcritureACategoriser,
)
from comptis.domain.categorization.value_objects import CategorizationSource, CategorizationStatut

DEFAULT_MIN_OCCURRENCE_THRESHOLD = 3
DEFAULT_CONFIDENCE_THRESHOLD = 0.85
_PATTERN_CONFIDENCE = 0.95


def _normalize_libelle(libelle: str) -> str:
    return libelle.strip().upper()


class CategorizeEcriture:
    """Categorizes an incoming journal-entry line against a PCG account.

    Checks for a trusted tenant-learned pattern first (a libelle seen often enough
    in the past for this tenant); falls back to the RAG-like AccountRetriever
    otherwise. Decides auto-validate vs. human-review based on a confidence
    threshold, then persists the resulting decision.
    """

    def __init__(
        self,
        pattern_repo: CategorizationPatternRepository,
        account_retriever: AccountRetriever,
        decision_repo: CategorizationDecisionRepository,
        min_occurrence_threshold: int = DEFAULT_MIN_OCCURRENCE_THRESHOLD,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._pattern_repo = pattern_repo
        self._account_retriever = account_retriever
        self._decision_repo = decision_repo
        self._min_occurrence_threshold = min_occurrence_threshold
        self._confidence_threshold = confidence_threshold

    async def _suggest(self, tenant_id: UUID, ecriture: EcritureACategoriser) -> CategorizationSuggestion:
        libelle_pattern = _normalize_libelle(ecriture.libelle)
        pattern = await self._pattern_repo.find_by_libelle(tenant_id, libelle_pattern)
        if pattern is not None and pattern.occurrence_count >= self._min_occurrence_threshold:
            return CategorizationSuggestion(
                compte_code=pattern.compte_code,
                confidence=_PATTERN_CONFIDENCE,
                source=CategorizationSource.PATTERN,
                evidence=[f"{pattern.libelle_pattern} -> {pattern.compte_code} (vu {pattern.occurrence_count} fois)"],
            )

        query = f"{ecriture.libelle} {ecriture.tiers}".strip()
        candidates = await self._account_retriever.search(query, top_k=5)
        if not candidates:
            return CategorizationSuggestion(compte_code="", confidence=0.0, source=CategorizationSource.RAG)
        return candidates[0]

    async def execute(self, tenant_id: UUID, ecriture: EcritureACategoriser) -> CategorizationDecision:
        suggestion = await self._suggest(tenant_id, ecriture)
        statut = (
            CategorizationStatut.AUTO_VALIDATED
            if suggestion.confidence >= self._confidence_threshold
            else CategorizationStatut.PENDING_REVIEW
        )
        decision = CategorizationDecision(
            id=uuid4(),
            tenant_id=tenant_id,
            ecriture_id=ecriture.id,
            compte_code=suggestion.compte_code,
            statut=statut,
            confidence=suggestion.confidence,
            validated_by=None,
        )
        await self._decision_repo.save(decision)
        return decision
