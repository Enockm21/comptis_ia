from __future__ import annotations

from rapidfuzz import fuzz, process, utils
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationSuggestion, CompteComptable
from comptis.domain.categorization.value_objects import CategorizationSource
from comptis.infrastructure.db.models import CompteComptableModel

_MIN_SCORE = 40.0  # rapidfuzz score is 0-100; below this a match is not worth surfacing


class RapidFuzzAccountRetriever:
    """Phase 1 implementation of the AccountRetriever port (see application/categorization/ports.py):
    fuzzy string matching between the query and each account's libelle, using rapidfuzz (already
    a project dependency). Holds the reference set (~27 seeded accounts today) in memory — cheap
    at this size. Swappable behind the AccountRetriever port for the future hybrid RAG
    implementation (ADR-002 phase 2) without touching any use case."""

    def __init__(self, comptes: list[CompteComptable]) -> None:
        self._comptes = comptes

    @property
    def comptes(self) -> list[CompteComptable]:
        """Exposed read-only for callers that need code->libelle lookups outside search()
        (e.g. the evaluation harness in scripts/eval_categorization.py)."""
        return self._comptes

    @classmethod
    async def load(cls, session: AsyncSession) -> "RapidFuzzAccountRetriever":
        result = await session.execute(select(CompteComptableModel))
        comptes = [
            CompteComptable(code=row.code, libelle=row.libelle, classe=row.classe)
            for row in result.scalars().all()
        ]
        return cls(comptes)

    async def search(self, query: str, top_k: int = 5) -> list[CategorizationSuggestion]:
        if not self._comptes:
            return []
        libelle_by_index = {i: c.libelle for i, c in enumerate(self._comptes)}
        matches = process.extract(
            query,
            libelle_by_index,
            scorer=fuzz.token_set_ratio,
            processor=utils.default_process,
            limit=top_k,
        )
        results: list[CategorizationSuggestion] = []
        for _libelle, score, index in matches:
            if score < _MIN_SCORE:
                continue
            compte = self._comptes[index]
            results.append(
                CategorizationSuggestion(
                    compte_code=compte.code,
                    confidence=score / 100.0,
                    source=CategorizationSource.RAG,
                    evidence=[f"{compte.code} {compte.libelle} (score {score:.0f})"],
                )
            )
        return results
