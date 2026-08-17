from __future__ import annotations

from typing import Protocol
from uuid import UUID

from comptis.domain.categorization.entities import (
    CategorizationDecision,
    CategorizationPattern,
    CategorizationSuggestion,
)


class CategorizationPatternRepository(Protocol):
    async def find_by_libelle(
        self, tenant_id: UUID, libelle_pattern: str
    ) -> CategorizationPattern | None: ...

    async def upsert(self, pattern: CategorizationPattern) -> CategorizationPattern: ...


class AccountRetriever(Protocol):
    """Abstracts account search. Phase 1: rapidfuzz over comptes_pcg. Phase 2 (future
    brick): hybrid RAG (dense + BM25 + reranking) — same port, different implementation."""

    async def search(self, query: str, top_k: int = 5) -> list[CategorizationSuggestion]: ...


class CategorizationDecisionRepository(Protocol):
    async def save(self, decision: CategorizationDecision) -> None: ...

    async def get_by_ecriture(self, ecriture_id: UUID) -> CategorizationDecision | None: ...
