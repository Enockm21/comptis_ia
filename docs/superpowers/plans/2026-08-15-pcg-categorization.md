# PCG Categorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a categorization brick that assigns a PCG (Plan Comptable Général) account to an incoming journal entry line, learning per-tenant patterns and falling back to fuzzy search over a reference chart of accounts.

**Architecture:** Clean Architecture layering matching the existing `tenancy` and `rapprochement` modules — `domain/categorization` (pure entities) → `application/categorization` (use cases + Protocol ports) → `infrastructure` (SQLAlchemy repos, RLS-scoped tables, a rapidfuzz-based `AccountRetriever`) → `interface/api/categorization` (FastAPI router). Phase 1 only: the `AccountRetriever` port is implemented with rapidfuzz fuzzy matching against a seeded `comptes_pcg` table, not the full hybrid RAG (Qdrant + BM25 + reranker) described in ADR-002 — that is a separate future brick, swappable behind the same port.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (asyncio), Alembic, rapidfuzz (already a dependency), pytest + pytest-asyncio, testcontainers-python, FastAPI.

**Spec:** `docs/superpowers/specs/2026-08-15-pcg-categorization-design.md`

## Global Constraints

- Confidence threshold for auto-validation: 0.85 (spec: "seuil de confiance ... défaut 85%")
- Minimum occurrence count before a tenant pattern is trusted: 3, injectable/configurable per use case instance (spec: confirmed by user)
- Only human-validated decisions update `CategorizationPattern` — auto-validations never write to the pattern table (spec: prevents self-reinforcing errors)
- RLS GUC name is `app.current_organization_id` (NOT `app.organization_id` — migration 0005 fixed exactly this bug for `reconciliation_patterns`; do not repeat it)
- Next migration revision is `0006`, `down_revision = "0005"`

---

## Task 1: Domain — value objects

**Files:**
- Create: `src/comptis/domain/categorization/__init__.py`
- Create: `src/comptis/domain/categorization/value_objects.py`
- Create: `tests/domain/categorization/__init__.py`
- Create: `tests/domain/categorization/test_value_objects.py`

**Interfaces:**
- Produces: `CategorizationSource` (StrEnum: `PATTERN`, `RAG`), `CategorizationStatut` (StrEnum: `AUTO_VALIDATED`, `PENDING_REVIEW`, `HUMAN_VALIDATED`)

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/categorization/test_value_objects.py
from comptis.domain.categorization.value_objects import CategorizationSource, CategorizationStatut


def test_categorization_source_values():
    assert CategorizationSource.PATTERN == "pattern"
    assert CategorizationSource.RAG == "rag"


def test_categorization_statut_values():
    assert CategorizationStatut.AUTO_VALIDATED == "auto_validated"
    assert CategorizationStatut.PENDING_REVIEW == "pending_review"
    assert CategorizationStatut.HUMAN_VALIDATED == "human_validated"


def test_categorization_source_is_string():
    assert isinstance(CategorizationSource.PATTERN, str)
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/domain/categorization/test_value_objects.py -v`
Expected: `ModuleNotFoundError: No module named 'comptis.domain.categorization'`

- [ ] **Step 3: Implement**

```python
# src/comptis/domain/categorization/__init__.py
```

```python
# src/comptis/domain/categorization/value_objects.py
from enum import StrEnum


class CategorizationSource(StrEnum):
    PATTERN = "pattern"
    RAG = "rag"


class CategorizationStatut(StrEnum):
    AUTO_VALIDATED = "auto_validated"
    PENDING_REVIEW = "pending_review"
    HUMAN_VALIDATED = "human_validated"
```

```python
# tests/domain/categorization/__init__.py
```

- [ ] **Step 4: Run to see them pass**

Run: `uv run pytest tests/domain/categorization/test_value_objects.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/comptis/domain/categorization/ tests/domain/categorization/
git commit -m "feat(domain): add categorization value objects"
```

---

## Task 2: Domain — entities

**Files:**
- Create: `src/comptis/domain/categorization/entities.py`
- Create: `tests/domain/categorization/test_entities.py`

**Interfaces:**
- Consumes: `CategorizationSource`, `CategorizationStatut` from Task 1
- Produces: `CompteComptable`, `EcritureACategoriser`, `CategorizationPattern`, `CategorizationSuggestion`, `CategorizationDecision` dataclasses — exact fields below, used by every later task

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/categorization/test_entities.py
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
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/domain/categorization/test_entities.py -v`
Expected: `ModuleNotFoundError: No module named 'comptis.domain.categorization.entities'`

- [ ] **Step 3: Implement**

```python
# src/comptis/domain/categorization/entities.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from comptis.domain.categorization.value_objects import CategorizationSource, CategorizationStatut


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class CompteComptable:
    code: str
    libelle: str
    classe: int


@dataclass
class EcritureACategoriser:
    id: UUID
    libelle: str
    montant: Decimal
    tiers: str
    date: date


@dataclass
class CategorizationPattern:
    tenant_id: UUID
    libelle_pattern: str
    fournisseur: str
    compte_code: str
    occurrence_count: int
    last_seen_at: datetime
    id: UUID = field(default_factory=uuid4)


@dataclass
class CategorizationSuggestion:
    compte_code: str
    confidence: float
    source: CategorizationSource
    evidence: list[str] = field(default_factory=list)


@dataclass
class CategorizationDecision:
    id: UUID
    tenant_id: UUID
    ecriture_id: UUID
    compte_code: str
    statut: CategorizationStatut
    confidence: float
    validated_by: UUID | None
    created_at: datetime = field(default_factory=_now)
```

- [ ] **Step 4: Run to see them pass**

Run: `uv run pytest tests/domain/categorization/test_entities.py -v`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/comptis/domain/categorization/entities.py tests/domain/categorization/test_entities.py
git commit -m "feat(domain): add categorization entities"
```

---

## Task 3: Domain — exceptions

**Files:**
- Create: `src/comptis/domain/categorization/exceptions.py`
- Create: `tests/domain/categorization/test_exceptions.py`

**Interfaces:**
- Produces: `CategorizationDecisionNotFoundError` — raised by `ValidateCategorization` (Task 6) when no prior decision exists for the écriture being validated

- [ ] **Step 1: Write the failing test**

```python
# tests/domain/categorization/test_exceptions.py
import pytest

from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError


def test_can_be_raised_and_caught():
    with pytest.raises(CategorizationDecisionNotFoundError, match="no decision"):
        raise CategorizationDecisionNotFoundError("no decision for this ecriture")
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/domain/categorization/test_exceptions.py -v`
Expected: `ModuleNotFoundError: No module named 'comptis.domain.categorization.exceptions'`

- [ ] **Step 3: Implement**

```python
# src/comptis/domain/categorization/exceptions.py
class CategorizationDecisionNotFoundError(Exception):
    """Raised when validating a decision that was never created by CategorizeEcriture."""
```

- [ ] **Step 4: Run to see it pass**

Run: `uv run pytest tests/domain/categorization/test_exceptions.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add src/comptis/domain/categorization/exceptions.py tests/domain/categorization/test_exceptions.py
git commit -m "feat(domain): add CategorizationDecisionNotFoundError"
```

---

## Task 4: Application — ports

**Files:**
- Create: `src/comptis/application/categorization/__init__.py`
- Create: `src/comptis/application/categorization/ports.py`

No dedicated test file — these are `Protocol` interfaces, validated implicitly by the fakes used in Task 4/5's use case tests (same convention as `application/rapprochement/ports.py` and `application/tenancy/ports.py`).

**Interfaces:**
- Consumes: `CategorizationPattern`, `CategorizationSuggestion`, `CategorizationDecision` from Task 2
- Produces: `CategorizationPatternRepository`, `AccountRetriever`, `CategorizationDecisionRepository` Protocols — exact method signatures used by Task 4/5 use cases and by every infrastructure implementation later

- [ ] **Step 1: Create `ports.py`**

```python
# src/comptis/application/categorization/__init__.py
```

```python
# src/comptis/application/categorization/ports.py
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
```

- [ ] **Step 2: Commit**

```bash
git add src/comptis/application/categorization/
git commit -m "feat(application): add categorization port Protocols"
```

---

## Task 5: Application — CategorizeEcriture use case

**Files:**
- Create: `src/comptis/application/categorization/use_cases.py`
- Create: `tests/application/categorization/__init__.py`
- Create: `tests/application/categorization/test_use_cases.py`

**Interfaces:**
- Consumes: `CategorizationPatternRepository`, `AccountRetriever`, `CategorizationDecisionRepository` (Task 4); `CategorizationPattern`, `CategorizationSuggestion`, `CategorizationDecision`, `EcritureACategoriser` (Task 2); `CategorizationSource`, `CategorizationStatut` (Task 1)
- Produces: `CategorizeEcriture` class with `__init__(self, pattern_repo, account_retriever, decision_repo, min_occurrence_threshold: int = 3, confidence_threshold: float = 0.85)` and `async def execute(self, tenant_id: UUID, ecriture: EcritureACategoriser) -> CategorizationDecision`. Also `_normalize_libelle(libelle: str) -> str` module-level helper, reused by Task 6.

- [ ] **Step 1: Write the failing tests**

```python
# tests/application/categorization/test_use_cases.py
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.application.categorization.use_cases import CategorizeEcriture
from comptis.domain.categorization.entities import (
    CategorizationDecision,
    CategorizationPattern,
    CategorizationSuggestion,
    EcritureACategoriser,
)
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
        for d in self.saved:
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
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/application/categorization/test_use_cases.py -v`
Expected: `ModuleNotFoundError: No module named 'comptis.application.categorization.use_cases'`

- [ ] **Step 3: Implement**

```python
# src/comptis/application/categorization/use_cases.py
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
```

```python
# tests/application/categorization/__init__.py
```

- [ ] **Step 4: Run to see them pass**

Run: `uv run pytest tests/application/categorization/test_use_cases.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add src/comptis/application/categorization/use_cases.py tests/application/categorization/
git commit -m "feat(application): add CategorizeEcriture use case"
```

---

## Task 6: Application — ValidateCategorization use case

**Files:**
- Modify: `src/comptis/application/categorization/use_cases.py`
- Modify: `tests/application/categorization/test_use_cases.py`

**Interfaces:**
- Consumes: `_normalize_libelle`, ports from Task 4/5; `CategorizationDecisionNotFoundError` (Task 3); `CategorizationPattern` (Task 2)
- Produces: `ValidateCategorization` class with `__init__(self, pattern_repo, decision_repo)` and `async def execute(self, tenant_id: UUID, ecriture: EcritureACategoriser, compte_code: str, validated_by: UUID) -> CategorizationDecision`

- [ ] **Step 1: Append the failing tests**

```python
# append to tests/application/categorization/test_use_cases.py
from comptis.application.categorization.use_cases import CategorizeEcriture, ValidateCategorization
from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError


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
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/application/categorization/test_use_cases.py -v`
Expected: `ImportError: cannot import name 'ValidateCategorization'`

- [ ] **Step 3: Implement — append to `use_cases.py`**

```python
# append to src/comptis/application/categorization/use_cases.py
from comptis.domain.categorization.entities import CategorizationPattern
from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError

_HUMAN_VALIDATED_CONFIDENCE = 1.0


class ValidateCategorization:
    def __init__(
        self,
        pattern_repo: CategorizationPatternRepository,
        decision_repo: CategorizationDecisionRepository,
    ) -> None:
        self._pattern_repo = pattern_repo
        self._decision_repo = decision_repo

    async def execute(
        self, tenant_id: UUID, ecriture: EcritureACategoriser, compte_code: str, validated_by: UUID,
    ) -> CategorizationDecision:
        existing = await self._decision_repo.get_by_ecriture(ecriture.id)
        if existing is None:
            raise CategorizationDecisionNotFoundError(
                f"no decision for ecriture {ecriture.id} — run CategorizeEcriture first"
            )

        updated = CategorizationDecision(
            id=existing.id,
            tenant_id=tenant_id,
            ecriture_id=ecriture.id,
            compte_code=compte_code,
            statut=CategorizationStatut.HUMAN_VALIDATED,
            confidence=_HUMAN_VALIDATED_CONFIDENCE,
            validated_by=validated_by,
            created_at=existing.created_at,
        )
        await self._decision_repo.save(updated)

        pattern = CategorizationPattern(
            tenant_id=tenant_id,
            libelle_pattern=_normalize_libelle(ecriture.libelle),
            fournisseur=ecriture.tiers,
            compte_code=compte_code,
            occurrence_count=1,
            last_seen_at=updated.created_at,
        )
        await self._pattern_repo.upsert(pattern)

        return updated
```

Note: `_FakeDecisionRepo.save` in the test fakes only appends — it does not overwrite an
existing entry with the same `ecriture_id`. Fix the fake so `get_by_ecriture` always returns the
most recent save for that `ecriture_id` (last-write-wins), matching how the real Postgres upsert
will behave in Task 9:

```python
# replace the FakeDecisionRepo.get_by_ecriture body in tests/application/categorization/test_use_cases.py
    async def get_by_ecriture(self, ecriture_id):
        for d in reversed(self.saved):
            if d.ecriture_id == ecriture_id:
                return d
        return None
```

- [ ] **Step 4: Run to see them pass**

Run: `uv run pytest tests/application/categorization/test_use_cases.py -v`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/comptis/application/categorization/use_cases.py tests/application/categorization/test_use_cases.py
git commit -m "feat(application): add ValidateCategorization use case with pattern learning"
```

---

## Task 7: Infrastructure — ORM models

**Files:**
- Modify: `src/comptis/infrastructure/db/models.py` (append at end of file)

No dedicated unit test — models are verified via the migration (Task 8) and integration tests
(Task 9), same convention as `tenancy`'s Task 7.

**Interfaces:**
- Produces: `CompteComptableModel` (table `comptes_pcg`), `CategorizationPatternModel` (table
  `categorization_patterns`), `CategorizationDecisionModel` (table `categorization_decisions`) —
  consumed by Task 8 (migration), Task 9 (repositories), Task 10 (rapidfuzz retriever reads
  `CompteComptableModel`)

- [ ] **Step 1: Append the model classes**

```python
# append to src/comptis/infrastructure/db/models.py
class CompteComptableModel(Base):
    __tablename__ = "comptes_pcg"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(sa.String(20), nullable=False, unique=True)
    libelle: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    classe: Mapped[int] = mapped_column(sa.Integer, nullable=False)


class CategorizationPatternModel(Base):
    __tablename__ = "categorization_patterns"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    libelle_pattern: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    fournisseur: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    compte_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "tenant_id", "libelle_pattern", "fournisseur", name="uq_cp_tenant_libelle_fournisseur"
        ),
    )


class CategorizationDecisionModel(Base):
    __tablename__ = "categorization_decisions"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    ecriture_id: Mapped[UUID] = mapped_column(sa.Uuid, nullable=False)
    compte_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    validated_by: Mapped[UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (sa.UniqueConstraint("ecriture_id", name="uq_cd_ecriture"),)
```

- [ ] **Step 2: Commit**

```bash
git add src/comptis/infrastructure/db/models.py
git commit -m "feat(infra): add ORM models for categorization"
```

---

## Task 8: Infrastructure — migration (tables, RLS, PCG seed data)

**Files:**
- Create: `src/comptis/infrastructure/db/migrations/versions/0006_add_categorization.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (raw SQL/Alembic `op` calls, independent of the ORM
  models in Task 7)
- Produces: tables `comptes_pcg` (seeded with ~26 common class-6 accounts), `categorization_patterns`,
  `categorization_decisions` — read by Task 9's repositories and Task 10's retriever

- [ ] **Step 1: Create the migration**

```python
# src/comptis/infrastructure/db/migrations/versions/0006_add_categorization.py
"""Add categorization tables: comptes_pcg (seeded), categorization_patterns, categorization_decisions

comptes_pcg is a global reference table (the French PCG chart of accounts) — it carries no
tenant_id and is not RLS-scoped, unlike every other table in this schema. It is read-only at
runtime for comptis_app (rows only change via a future migration, not application code).

categorization_patterns and categorization_decisions follow the exact same RLS shape as
reconciliation_patterns, using the correct GUC name from the start: 'app.current_organization_id'
(migration 0005 had to retrofix this exact mistake for reconciliation_patterns — see its docstring).

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-15
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (code, libelle, classe) — starter subset of common PME class-6 (charges) accounts from the
# official French PCG. Extend this list in a future migration as coverage gaps are found via
# the evaluation harness (see plan Task 12 / spec §Niveau 4).
_PCG_SEED_ACCOUNTS: list[tuple[str, str, int]] = [
    ("606100", "Achats non stockés de fournitures - eau, énergie", 6),
    ("606400", "Fournitures administratives", 6),
    ("606800", "Autres matières et fournitures", 6),
    ("611000", "Sous-traitance générale", 6),
    ("613200", "Locations immobilières", 6),
    ("613500", "Locations mobilières", 6),
    ("614000", "Charges locatives et de copropriété", 6),
    ("615500", "Entretien et réparations sur biens mobiliers", 6),
    ("615600", "Entretien et réparations sur biens immobiliers", 6),
    ("616100", "Primes d'assurance", 6),
    ("618300", "Documentation technique", 6),
    ("621000", "Personnel extérieur à l'entreprise", 6),
    ("622600", "Honoraires", 6),
    ("622700", "Frais d'actes et de contentieux", 6),
    ("623100", "Annonces et insertions publicitaires", 6),
    ("623400", "Cadeaux à la clientèle", 6),
    ("624100", "Transports sur achats", 6),
    ("624200", "Transports sur ventes", 6),
    ("625100", "Voyages et déplacements", 6),
    ("625600", "Missions", 6),
    ("625700", "Réceptions", 6),
    ("626100", "Frais postaux et de télécommunications", 6),
    ("627000", "Services bancaires et assimilés", 6),
    ("635800", "Autres droits d'enregistrement et de timbre", 6),
    ("641100", "Salaires, appointements", 6),
    ("645100", "Cotisations à l'URSSAF", 6),
]


def upgrade() -> None:
    # --- comptes_pcg: global reference table, no RLS ---
    op.create_table(
        "comptes_pcg",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("classe", sa.Integer, nullable=False),
    )
    comptes_pcg_table = sa.table(
        "comptes_pcg",
        sa.column("id", sa.Uuid),
        sa.column("code", sa.String),
        sa.column("libelle", sa.String),
        sa.column("classe", sa.Integer),
    )
    op.bulk_insert(
        comptes_pcg_table,
        [
            {"id": uuid.uuid4(), "code": code, "libelle": libelle, "classe": classe}
            for code, libelle, classe in _PCG_SEED_ACCOUNTS
        ],
    )
    op.execute("GRANT SELECT ON comptes_pcg TO comptis_app")

    # --- categorization_patterns ---
    op.create_table(
        "categorization_patterns",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("libelle_pattern", sa.String(255), nullable=False),
        sa.Column("fournisseur", sa.String(255), nullable=False),
        sa.Column("compte_code", sa.String(20), nullable=False),
        sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "libelle_pattern", "fournisseur", name="uq_cp_tenant_libelle_fournisseur"
        ),
    )
    op.create_index(
        "ix_categorization_patterns_tenant_libelle",
        "categorization_patterns",
        ["tenant_id", "libelle_pattern"],
    )
    op.execute("ALTER TABLE categorization_patterns ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE categorization_patterns FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY cp_org_isolation ON categorization_patterns
            USING (
                tenant_id IN (
                    SELECT id FROM tenants
                    WHERE organization_id = current_setting('app.current_organization_id', true)::uuid
                )
            )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON categorization_patterns TO comptis_app")

    # --- categorization_decisions ---
    op.create_table(
        "categorization_decisions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("ecriture_id", sa.Uuid, nullable=False),
        sa.Column("compte_code", sa.String(20), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column(
            "validated_by", sa.Uuid, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("ecriture_id", name="uq_cd_ecriture"),
    )
    op.execute("ALTER TABLE categorization_decisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE categorization_decisions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY cd_org_isolation ON categorization_decisions
            USING (
                tenant_id IN (
                    SELECT id FROM tenants
                    WHERE organization_id = current_setting('app.current_organization_id', true)::uuid
                )
            )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON categorization_decisions TO comptis_app")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON categorization_decisions FROM comptis_app")
    op.execute("DROP POLICY IF EXISTS cd_org_isolation ON categorization_decisions")
    op.drop_table("categorization_decisions")

    op.execute("REVOKE ALL PRIVILEGES ON categorization_patterns FROM comptis_app")
    op.execute("DROP POLICY IF EXISTS cp_org_isolation ON categorization_patterns")
    op.drop_index("ix_categorization_patterns_tenant_libelle", table_name="categorization_patterns")
    op.drop_table("categorization_patterns")

    op.execute("REVOKE ALL PRIVILEGES ON comptes_pcg FROM comptis_app")
    op.drop_table("comptes_pcg")
```

- [ ] **Step 2: Run the migration against a local Postgres**

```bash
docker compose up -d postgres
uv run alembic upgrade head
```

Expected output ends with: `Running upgrade 0005 -> 0006, Add categorization tables...`

- [ ] **Step 3: Verify the seed data landed**

```bash
uv run python -c "
import asyncio, os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'])
    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT count(*) FROM comptes_pcg'))
        print('comptes_pcg rows:', result.scalar())

asyncio.run(main())
"
```

Expected: `comptes_pcg rows: 26`

- [ ] **Step 4: Commit**

```bash
git add src/comptis/infrastructure/db/migrations/versions/0006_add_categorization.py
git commit -m "feat(infra): add categorization migration with seeded PCG reference table"
```

---

## Task 9: Infrastructure — pattern and decision repositories

**Files:**
- Create: `src/comptis/infrastructure/db/categorization_patterns.py`
- Create: `src/comptis/infrastructure/db/categorization_decisions.py`
- Create: `tests/infrastructure/db/categorization/__init__.py`
- Create: `tests/infrastructure/db/categorization/conftest.py`
- Create: `tests/infrastructure/db/categorization/test_pattern_repository.py`
- Create: `tests/infrastructure/db/categorization/test_decision_repository.py`

**Interfaces:**
- Consumes: `CategorizationPatternModel`, `CategorizationDecisionModel` (Task 7); tables from
  migration 0006 (Task 8); `CategorizationPattern`, `CategorizationDecision` (Task 2)
- Produces: `SQLAlchemyCategorizationPatternRepository`, `SQLAlchemyCategorizationDecisionRepository`
  — implement the Task 4 ports, wired into the router in Task 11

- [ ] **Step 1: Create the testcontainers conftest**

```python
# tests/infrastructure/db/categorization/conftest.py
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16", username="postgres", password="test", dbname="comptis_test") as pg:
        yield pg


@pytest.fixture(scope="session")
def admin_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+psycopg://postgres:test@{host}:{port}/comptis_test"


@pytest.fixture(scope="session")
def app_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://comptis_app:app_secret@{host}:{port}/comptis_test"


@pytest.fixture(scope="session", autouse=True)
def run_migrations(admin_db_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", admin_db_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_engine(admin_db_url):
    engine = create_async_engine(
        admin_db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://"), echo=False
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_engine(app_db_url):
    engine = create_async_engine(app_db_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(app_engine):
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            yield session
            await session.rollback()
```

```python
# tests/infrastructure/db/categorization/__init__.py
```

- [ ] **Step 2: Write the failing pattern repository test**

```python
# tests/infrastructure/db/categorization/test_pattern_repository.py
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationPattern
from comptis.infrastructure.db.categorization_patterns import SQLAlchemyCategorizationPatternRepository
from comptis.infrastructure.db.models import CategorizationPatternModel

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_tenant(admin_engine):
    org_id = uuid4()
    tenant_id = uuid4()
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO organizations (id, name, type, created_at) VALUES (:id, :name, :type, now())"),
                {"id": str(org_id), "name": "Test Org", "type": "cabinet"},
            )
            await session.execute(
                text("INSERT INTO tenants (id, organization_id, name, created_at) VALUES (:id, :org_id, :name, now())"),
                {"id": str(tenant_id), "org_id": str(org_id), "name": "Test Tenant"},
            )
    return tenant_id, org_id


async def _set_rls_context(session: AsyncSession, org_id) -> None:
    await session.execute(
        text("SELECT set_config('app.current_organization_id', :value, true)"),
        {"value": str(org_id)},
    )


@pytest.mark.integration
async def test_upsert_new_pattern(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationPatternRepository(db_session)

    pattern = CategorizationPattern(
        tenant_id=tenant_id, libelle_pattern="BRETAGNE TELECOM", fournisseur="Bretagne Telecom",
        compte_code="626100", occurrence_count=1, last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    saved = await repo.upsert(pattern)
    assert saved.compte_code == "626100"
    assert saved.occurrence_count == 1


@pytest.mark.integration
async def test_upsert_increments_and_overrides_compte(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationPatternRepository(db_session)

    first = CategorizationPattern(
        tenant_id=tenant_id, libelle_pattern="SIEMENS", fournisseur="Siemens Lease",
        compte_code="613500", occurrence_count=1, last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    await repo.upsert(first)

    corrected = CategorizationPattern(
        tenant_id=tenant_id, libelle_pattern="SIEMENS", fournisseur="Siemens Lease",
        compte_code="615500", occurrence_count=1, last_seen_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    updated = await repo.upsert(corrected)
    assert updated.occurrence_count == 2
    assert updated.compte_code == "615500"


@pytest.mark.integration
async def test_find_by_libelle_none(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationPatternRepository(db_session)
    result = await repo.find_by_libelle(tenant_id, "NONEXISTENT")
    assert result is None


@pytest.mark.integration
async def test_other_org_cannot_see_pattern(seeded_tenant, admin_engine, app_engine):
    """Seed via admin_engine (superuser, real commit, bypasses RLS) so the row genuinely
    persists — then read via app_engine scoped to a *different* org. Using db_session for
    the write here would be wrong: that fixture wraps the test in an open transaction that
    always rolls back, so a separate session would never see the row regardless of RLS,
    and the test would pass for the wrong reason."""
    tenant_id, org_id = seeded_tenant
    async with AsyncSession(admin_engine, expire_on_commit=False) as seed_session:
        async with seed_session.begin():
            seed_session.add(CategorizationPatternModel(
                id=uuid4(), tenant_id=tenant_id, libelle_pattern="ISOLATED", fournisseur="X",
                compte_code="626100", occurrence_count=1, last_seen_at=datetime.now(tz=timezone.utc),
            ))

    other_org_id = uuid4()
    async with AsyncSession(app_engine, expire_on_commit=False) as other_session:
        async with other_session.begin():
            await _set_rls_context(other_session, other_org_id)
            other_repo = SQLAlchemyCategorizationPatternRepository(other_session)
            result = await other_repo.find_by_libelle(tenant_id, "ISOLATED")
            assert result is None, "RLS leak: other org can see this org's categorization pattern"
```

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/infrastructure/db/categorization/test_pattern_repository.py -v -m integration`
Expected: `ModuleNotFoundError: No module named 'comptis.infrastructure.db.categorization_patterns'`

- [ ] **Step 4: Implement `categorization_patterns.py`**

```python
# src/comptis/infrastructure/db/categorization_patterns.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationPattern
from comptis.infrastructure.db.models import CategorizationPatternModel


class SQLAlchemyCategorizationPatternRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_libelle(self, tenant_id: UUID, libelle_pattern: str) -> CategorizationPattern | None:
        stmt = (
            select(CategorizationPatternModel)
            .where(
                CategorizationPatternModel.tenant_id == tenant_id,
                CategorizationPatternModel.libelle_pattern == libelle_pattern,
            )
            .order_by(
                CategorizationPatternModel.occurrence_count.desc(),
                CategorizationPatternModel.last_seen_at.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def upsert(self, pattern: CategorizationPattern) -> CategorizationPattern:
        stmt = (
            insert(CategorizationPatternModel)
            .values(
                id=pattern.id,
                tenant_id=pattern.tenant_id,
                libelle_pattern=pattern.libelle_pattern,
                fournisseur=pattern.fournisseur,
                compte_code=pattern.compte_code,
                occurrence_count=pattern.occurrence_count,
                last_seen_at=pattern.last_seen_at,
            )
            .on_conflict_do_update(
                constraint="uq_cp_tenant_libelle_fournisseur",
                set_={
                    # A later human correction overrides the compte_code on file, not just
                    # the occurrence count — the accountant is telling us this libelle now
                    # maps to a (possibly different) account.
                    "compte_code": pattern.compte_code,
                    "occurrence_count": CategorizationPatternModel.occurrence_count + 1,
                    "last_seen_at": datetime.now(tz=timezone.utc),
                },
            )
            .returning(CategorizationPatternModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: CategorizationPatternModel) -> CategorizationPattern:
        return CategorizationPattern(
            id=row.id,
            tenant_id=row.tenant_id,
            libelle_pattern=row.libelle_pattern,
            fournisseur=row.fournisseur,
            compte_code=row.compte_code,
            occurrence_count=row.occurrence_count,
            last_seen_at=row.last_seen_at,
        )
```

- [ ] **Step 5: Run to see the pattern repository tests pass**

Run: `uv run pytest tests/infrastructure/db/categorization/test_pattern_repository.py -v -m integration`
Expected: `4 passed`

- [ ] **Step 6: Write the failing decision repository test**

```python
# tests/infrastructure/db/categorization/test_decision_repository.py
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationDecision
from comptis.domain.categorization.value_objects import CategorizationStatut
from comptis.infrastructure.db.categorization_decisions import SQLAlchemyCategorizationDecisionRepository

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_tenant(admin_engine):
    org_id = uuid4()
    tenant_id = uuid4()
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO organizations (id, name, type, created_at) VALUES (:id, :name, :type, now())"),
                {"id": str(org_id), "name": "Test Org", "type": "cabinet"},
            )
            await session.execute(
                text("INSERT INTO tenants (id, organization_id, name, created_at) VALUES (:id, :org_id, :name, now())"),
                {"id": str(tenant_id), "org_id": str(org_id), "name": "Test Tenant"},
            )
    return tenant_id, org_id


async def _set_rls_context(session: AsyncSession, org_id) -> None:
    await session.execute(
        text("SELECT set_config('app.current_organization_id', :value, true)"),
        {"value": str(org_id)},
    )


@pytest.mark.integration
async def test_save_and_get_by_ecriture(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationDecisionRepository(db_session)

    ecriture_id = uuid4()
    decision = CategorizationDecision(
        id=uuid4(), tenant_id=tenant_id, ecriture_id=ecriture_id, compte_code="626100",
        statut=CategorizationStatut.AUTO_VALIDATED, confidence=0.9, validated_by=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    await repo.save(decision)
    fetched = await repo.get_by_ecriture(ecriture_id)
    assert fetched is not None
    assert fetched.compte_code == "626100"
    assert fetched.statut == CategorizationStatut.AUTO_VALIDATED


@pytest.mark.integration
async def test_save_upserts_by_ecriture(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationDecisionRepository(db_session)

    ecriture_id = uuid4()
    original_id = uuid4()
    pending = CategorizationDecision(
        id=original_id, tenant_id=tenant_id, ecriture_id=ecriture_id, compte_code="626100",
        statut=CategorizationStatut.PENDING_REVIEW, confidence=0.4, validated_by=None,
        created_at=datetime.now(tz=timezone.utc),
    )
    await repo.save(pending)

    validated_by = uuid4()
    validated = CategorizationDecision(
        id=original_id, tenant_id=tenant_id, ecriture_id=ecriture_id, compte_code="613500",
        statut=CategorizationStatut.HUMAN_VALIDATED, confidence=1.0, validated_by=validated_by,
        created_at=pending.created_at,
    )
    await repo.save(validated)

    fetched = await repo.get_by_ecriture(ecriture_id)
    assert fetched.statut == CategorizationStatut.HUMAN_VALIDATED
    assert fetched.compte_code == "613500"
    assert fetched.validated_by == validated_by


@pytest.mark.integration
async def test_get_by_ecriture_none(db_session: AsyncSession, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await _set_rls_context(db_session, org_id)
    repo = SQLAlchemyCategorizationDecisionRepository(db_session)
    result = await repo.get_by_ecriture(uuid4())
    assert result is None
```

- [ ] **Step 7: Run to see them fail**

Run: `uv run pytest tests/infrastructure/db/categorization/test_decision_repository.py -v -m integration`
Expected: `ModuleNotFoundError: No module named 'comptis.infrastructure.db.categorization_decisions'`

- [ ] **Step 8: Implement `categorization_decisions.py`**

```python
# src/comptis/infrastructure/db/categorization_decisions.py
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationDecision
from comptis.domain.categorization.value_objects import CategorizationStatut
from comptis.infrastructure.db.models import CategorizationDecisionModel


class SQLAlchemyCategorizationDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, decision: CategorizationDecision) -> None:
        stmt = (
            insert(CategorizationDecisionModel)
            .values(
                id=decision.id,
                tenant_id=decision.tenant_id,
                ecriture_id=decision.ecriture_id,
                compte_code=decision.compte_code,
                statut=decision.statut.value,
                confidence=decision.confidence,
                validated_by=decision.validated_by,
                created_at=decision.created_at,
            )
            .on_conflict_do_update(
                constraint="uq_cd_ecriture",
                set_={
                    "compte_code": decision.compte_code,
                    "statut": decision.statut.value,
                    "confidence": decision.confidence,
                    "validated_by": decision.validated_by,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_by_ecriture(self, ecriture_id: UUID) -> CategorizationDecision | None:
        result = await self._session.execute(
            select(CategorizationDecisionModel).where(
                CategorizationDecisionModel.ecriture_id == ecriture_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return CategorizationDecision(
            id=row.id,
            tenant_id=row.tenant_id,
            ecriture_id=row.ecriture_id,
            compte_code=row.compte_code,
            statut=CategorizationStatut(row.statut),
            confidence=row.confidence,
            validated_by=row.validated_by,
            created_at=row.created_at,
        )
```

- [ ] **Step 9: Run to see them pass**

Run: `uv run pytest tests/infrastructure/db/categorization/test_decision_repository.py -v -m integration`
Expected: `3 passed`

- [ ] **Step 10: Commit**

```bash
git add src/comptis/infrastructure/db/categorization_patterns.py src/comptis/infrastructure/db/categorization_decisions.py tests/infrastructure/db/categorization/
git commit -m "feat(infra): add categorization pattern and decision repositories"
```

---

## Task 10: Infrastructure — RapidFuzzAccountRetriever

**Files:**
- Create: `src/comptis/infrastructure/categorization/__init__.py`
- Create: `src/comptis/infrastructure/categorization/rapidfuzz_retriever.py`
- Create: `tests/infrastructure/categorization/__init__.py`
- Create: `tests/infrastructure/categorization/test_rapidfuzz_retriever.py`
- Create: `tests/infrastructure/db/categorization/test_rapidfuzz_retriever_load.py`

**Interfaces:**
- Consumes: `CompteComptable`, `CategorizationSuggestion` (Task 2); `CategorizationSource` (Task 1);
  `CompteComptableModel` (Task 7, table seeded by Task 8)
- Produces: `RapidFuzzAccountRetriever` — implements the `AccountRetriever` port from Task 4,
  wired into the router in Task 11

- [ ] **Step 1: Write the failing pure-logic tests (no DB)**

```python
# tests/infrastructure/categorization/test_rapidfuzz_retriever.py
import pytest

from comptis.domain.categorization.entities import CompteComptable
from comptis.domain.categorization.value_objects import CategorizationSource
from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever


def _comptes() -> list[CompteComptable]:
    return [
        CompteComptable(code="626100", libelle="Frais postaux et de télécommunications", classe=6),
        CompteComptable(code="613500", libelle="Locations mobilières", classe=6),
        CompteComptable(code="625700", libelle="Réceptions", classe=6),
    ]


async def test_search_finds_close_match():
    retriever = RapidFuzzAccountRetriever(_comptes())
    results = await retriever.search("FRAIS TELECOMMUNICATIONS", top_k=3)
    assert results
    assert results[0].compte_code == "626100"
    assert results[0].source == CategorizationSource.RAG
    assert 0.0 < results[0].confidence <= 1.0


async def test_search_excludes_weak_matches():
    retriever = RapidFuzzAccountRetriever(_comptes())
    results = await retriever.search("XYZQWERTY UNRELATED TEXT 12345", top_k=3)
    assert all(r.confidence >= 0.4 for r in results)


async def test_search_on_empty_reference_set_returns_empty():
    retriever = RapidFuzzAccountRetriever([])
    results = await retriever.search("anything")
    assert results == []


async def test_search_result_carries_evidence():
    retriever = RapidFuzzAccountRetriever(_comptes())
    results = await retriever.search("RECEPTION CLIENT", top_k=1)
    assert results[0].evidence
    assert "625700" in results[0].evidence[0]


def test_comptes_property_exposes_reference_set():
    comptes = _comptes()
    retriever = RapidFuzzAccountRetriever(comptes)
    assert retriever.comptes == comptes
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/infrastructure/categorization/test_rapidfuzz_retriever.py -v`
Expected: `ModuleNotFoundError: No module named 'comptis.infrastructure.categorization'`

- [ ] **Step 3: Implement**

```python
# src/comptis/infrastructure/categorization/__init__.py
```

```python
# src/comptis/infrastructure/categorization/rapidfuzz_retriever.py
from __future__ import annotations

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationSuggestion, CompteComptable
from comptis.domain.categorization.value_objects import CategorizationSource
from comptis.infrastructure.db.models import CompteComptableModel

_MIN_SCORE = 40.0  # rapidfuzz score is 0-100; below this a match is not worth surfacing


class RapidFuzzAccountRetriever:
    """Phase 1 implementation of the AccountRetriever port (see application/categorization/ports.py):
    fuzzy string matching between the query and each account's libelle, using rapidfuzz (already
    a project dependency). Holds the reference set (~26 seeded accounts today) in memory — cheap
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
        matches = process.extract(query, libelle_by_index, scorer=fuzz.token_set_ratio, limit=top_k)
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
```

```python
# tests/infrastructure/categorization/__init__.py
```

- [ ] **Step 4: Run to see them pass**

Run: `uv run pytest tests/infrastructure/categorization/test_rapidfuzz_retriever.py -v`
Expected: `5 passed`

- [ ] **Step 5: Write the failing integration test for `load()`**

```python
# tests/infrastructure/db/categorization/test_rapidfuzz_retriever_load.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_load_reads_seeded_pcg_accounts(db_session: AsyncSession):
    retriever = await RapidFuzzAccountRetriever.load(db_session)
    results = await retriever.search("FRAIS TELECOMMUNICATIONS", top_k=1)
    assert results
    assert results[0].compte_code == "626100"
```

This test reuses the `db_session` fixture already defined in
`tests/infrastructure/db/categorization/conftest.py` (Task 9) — no new conftest needed, since the
`comptes_pcg` table is a global reference table seeded once by migration 0006, not tenant-scoped.

- [ ] **Step 6: Run to see it fail, then implement is already done in Step 3 — run to see it pass**

Run: `uv run pytest tests/infrastructure/db/categorization/test_rapidfuzz_retriever_load.py -v -m integration`
Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add src/comptis/infrastructure/categorization/ tests/infrastructure/categorization/ tests/infrastructure/db/categorization/test_rapidfuzz_retriever_load.py
git commit -m "feat(infra): add RapidFuzzAccountRetriever (phase-1 AccountRetriever)"
```

---

## Task 11: Interface — schemas, router, and API tests

**Files:**
- Create: `src/comptis/interface/api/categorization/__init__.py`
- Create: `src/comptis/interface/api/categorization/schemas.py`
- Create: `src/comptis/interface/api/categorization/router.py`
- Modify: `src/comptis/interface/api/main.py`
- Create: `tests/interface/api/test_categorization.py`

**Interfaces:**
- Consumes: `CategorizeEcriture`, `ValidateCategorization` (Task 5/6);
  `SQLAlchemyCategorizationPatternRepository`, `SQLAlchemyCategorizationDecisionRepository` (Task 9);
  `RapidFuzzAccountRetriever` (Task 10); `EcritureACategoriser` (Task 2);
  `CategorizationDecisionNotFoundError` (Task 3); `get_db_session`, `require_user`
  (`interface/api/dependencies.py`, pre-existing); `set_tenant_context`
  (`infrastructure/db/tenant_context.py`, pre-existing); `SQLAlchemyTenantRepository`
  (`infrastructure/db/repositories.py`, pre-existing)
- Produces: `POST /categorization/categorize`, `POST /categorization/validate` — the only two
  endpoints this brick exposes, matching the two use cases; no "list pending" endpoint (out of
  scope, YAGNI — add when a review UI needs it)

- [ ] **Step 1: Write the failing API tests**

Reuses the existing `tests/interface/api/conftest.py` fixtures (`client`, `admin_token`,
`admin_tenant_id`) — no new conftest needed.

```python
# tests/interface/api/test_categorization.py
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _ecriture_payload(libelle="TOULOUSE SELF STOCKAGE", tiers="Toulouse Self Stockage"):
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "libelle": libelle,
        "montant": "90.00",
        "tiers": tiers,
        "date": "2024-02-08",
    }


@pytest.mark.integration
async def test_categorize_requires_auth(client):
    resp = await client.post("/categorization/categorize", json={
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "ecriture": _ecriture_payload(),
    })
    assert resp.status_code == 401


@pytest.mark.integration
async def test_categorize_rejects_unknown_tenant(client, admin_token: str):
    resp = await client.post(
        "/categorization/categorize",
        json={
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "ecriture": _ecriture_payload(),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_categorize_returns_a_decision(client, admin_token: str, admin_tenant_id: str):
    resp = await client.post(
        "/categorization/categorize",
        json={"tenant_id": admin_tenant_id, "ecriture": _ecriture_payload()},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["statut"] in ("auto_validated", "pending_review")
    assert "id" in body


@pytest.mark.integration
async def test_validate_after_categorize_learns_pattern(client, admin_token: str, admin_tenant_id: str):
    payload = _ecriture_payload(libelle="SIEMENS LEASE 02", tiers="Siemens Lease")
    payload["id"] = "33333333-3333-3333-3333-333333333333"

    cat_resp = await client.post(
        "/categorization/categorize",
        json={"tenant_id": admin_tenant_id, "ecriture": payload},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cat_resp.status_code == 200

    val_resp = await client.post(
        "/categorization/validate",
        json={"tenant_id": admin_tenant_id, "ecriture": payload, "compte_code": "613500"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert val_resp.status_code == 200
    body = val_resp.json()
    assert body["statut"] == "human_validated"
    assert body["compte_code"] == "613500"
    assert body["validated_by"] is not None


@pytest.mark.integration
async def test_validate_unknown_ecriture_returns_404(client, admin_token: str, admin_tenant_id: str):
    payload = _ecriture_payload()
    payload["id"] = "44444444-4444-4444-4444-444444444444"
    resp = await client.post(
        "/categorization/validate",
        json={"tenant_id": admin_tenant_id, "ecriture": payload, "compte_code": "613500"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/interface/api/test_categorization.py -v -m integration`
Expected: `404` for every request (route doesn't exist yet) — the first two tests
(`test_categorize_requires_auth`, `test_categorize_rejects_unknown_tenant`) will fail because
they expect `401`/`404` for different reasons than "route not found", and the rest fail on
`assert resp.status_code == 200`.

- [ ] **Step 3: Create the schemas**

```python
# src/comptis/interface/api/categorization/__init__.py
```

```python
# src/comptis/interface/api/categorization/schemas.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class EcritureSchema(BaseModel):
    id: UUID
    libelle: str
    montant: Decimal
    tiers: str
    date: date


class CategorizeRequest(BaseModel):
    tenant_id: UUID
    ecriture: EcritureSchema


class ValidateRequest(BaseModel):
    tenant_id: UUID
    ecriture: EcritureSchema
    compte_code: str


class DecisionResponse(BaseModel):
    id: UUID
    ecriture_id: UUID
    compte_code: str
    statut: str
    confidence: float
    validated_by: UUID | None
    created_at: datetime
```

- [ ] **Step 4: Create the router**

```python
# src/comptis/interface/api/categorization/router.py
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.categorization.use_cases import CategorizeEcriture, ValidateCategorization
from comptis.domain.categorization.entities import CategorizationDecision, EcritureACategoriser
from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError
from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever
from comptis.infrastructure.db.categorization_decisions import SQLAlchemyCategorizationDecisionRepository
from comptis.infrastructure.db.categorization_patterns import SQLAlchemyCategorizationPatternRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.categorization.schemas import (
    CategorizeRequest,
    DecisionResponse,
    ValidateRequest,
)
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/categorization", tags=["categorization"])


async def _require_tenant_access(tenant_id: uuid.UUID, session: AsyncSession):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _to_response(decision: CategorizationDecision) -> DecisionResponse:
    return DecisionResponse(
        id=decision.id,
        ecriture_id=decision.ecriture_id,
        compte_code=decision.compte_code,
        statut=decision.statut.value,
        confidence=decision.confidence,
        validated_by=decision.validated_by,
        created_at=decision.created_at,
    )


def _to_domain_ecriture(body_ecriture) -> EcritureACategoriser:
    return EcritureACategoriser(
        id=body_ecriture.id,
        libelle=body_ecriture.libelle,
        montant=body_ecriture.montant,
        tiers=body_ecriture.tiers,
        date=body_ecriture.date,
    )


@router.post("/categorize", response_model=DecisionResponse)
async def categorize(
    body: CategorizeRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    tenant = await _require_tenant_access(body.tenant_id, session)
    await set_tenant_context(
        session, organization_id=tenant.organization_id, tenant_id=body.tenant_id, user_id=user_id
    )
    use_case = CategorizeEcriture(
        pattern_repo=SQLAlchemyCategorizationPatternRepository(session),
        account_retriever=await RapidFuzzAccountRetriever.load(session),
        decision_repo=SQLAlchemyCategorizationDecisionRepository(session),
    )
    decision = await use_case.execute(tenant_id=body.tenant_id, ecriture=_to_domain_ecriture(body.ecriture))
    return _to_response(decision)


@router.post("/validate", response_model=DecisionResponse)
async def validate(
    body: ValidateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    tenant = await _require_tenant_access(body.tenant_id, session)
    await set_tenant_context(
        session, organization_id=tenant.organization_id, tenant_id=body.tenant_id, user_id=user_id
    )
    use_case = ValidateCategorization(
        pattern_repo=SQLAlchemyCategorizationPatternRepository(session),
        decision_repo=SQLAlchemyCategorizationDecisionRepository(session),
    )
    try:
        decision = await use_case.execute(
            tenant_id=body.tenant_id,
            ecriture=_to_domain_ecriture(body.ecriture),
            compte_code=body.compte_code,
            validated_by=user_id,
        )
    except CategorizationDecisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(decision)
```

- [ ] **Step 5: Register the router in `main.py`**

```python
# src/comptis/interface/api/main.py
# Add this import alongside the existing router imports:
from comptis.interface.api.categorization.router import router as categorization_router

# Add this line alongside the existing app.include_router(...) calls:
app.include_router(categorization_router)
```

- [ ] **Step 6: Run to see the tests pass**

Run: `uv run pytest tests/interface/api/test_categorization.py -v -m integration`
Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add src/comptis/interface/api/categorization/ src/comptis/interface/api/main.py tests/interface/api/test_categorization.py
git commit -m "feat(interface): add categorization router with categorize and validate endpoints"
```

---

## Task 12: Evaluation harness (local, real PNI data — not part of the pytest suite)

**Files:**
- Create: `scripts/eval_categorization.py`
- Modify: `pyproject.toml` (add `openpyxl` to the `dev` dependency group — only this local script
  needs it, not the running application)

**Interfaces:**
- Consumes: `CategorizeEcriture` (Task 5); `EcritureACategoriser` (Task 2);
  `RapidFuzzAccountRetriever` including its `.comptes` property (Task 10)
- Produces: a standalone CLI script — no other task depends on it

This implements spec §"Niveau 4 — Évaluation". It is explicitly **not** wired into CI or pytest:
it requires a real local export file that is never committed (see [[project_pni_pilot]] memory —
treat this as sensitive real business data). The script itself contains no real data, only
generic parsing/scoring logic, so it is safe to commit.

Because PNiCompta's internal `Intitulé` labels (e.g. "FRAIS TELECOMMUNICATIONS") don't map 1:1 to
official PCG codes without manual curation, the script reports a **heuristic proxy metric** (fuzzy
text overlap between the predicted account's libelle and the export's own `Intitulé` column) —
not a strict ground-truth accuracy. It prints a full per-row table so the user can eyeball real
mismatches, which is the actual point: deciding whether phase-1 rapidfuzz is good enough or
whether the hybrid RAG brick (ADR-002 phase 2) is needed sooner.

- [ ] **Step 1: Add `openpyxl` to dev dependencies**

```toml
# pyproject.toml — inside [dependency-groups] dev = [...]
    "openpyxl>=3.1",
```

```bash
uv sync
```

- [ ] **Step 2: Write the script**

```python
#!/usr/bin/env python3
"""Local evaluation harness for the PCG categorization brick (spec: docs/superpowers/specs/
2026-08-15-pcg-categorization-design.md, "Niveau 4"). Not part of the pytest suite.

Replays a real "Edition Journaux" export (PNiCompta) against CategorizeEcriture and reports a
heuristic proxy match rate — fuzzy text overlap between the predicted account's libelle and the
export's own Intitulé column. This is NOT a strict ground-truth comparison: PNiCompta's internal
Intitulé labels don't map 1:1 to official PCG codes without manual curation. Read the printed
per-row table to judge real mismatches.

Requires a local Postgres with migrations applied (comptes_pcg must be seeded):
    docker compose up -d postgres
    uv run alembic upgrade head

Usage:
    uv run python scripts/eval_categorization.py /path/to/edition-journaux.xlsx

The input file must never be committed to the repo.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

import openpyxl
from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from comptis.application.categorization.use_cases import CategorizeEcriture
from comptis.domain.categorization.entities import CategorizationPattern, EcritureACategoriser
from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever

_PLAUSIBLE_MATCH_THRESHOLD = 50.0  # rapidfuzz score 0-100 — heuristic proxy, not ground truth


class _NullPatternRepo:
    """Always misses. This harness measures the phase-1 RAG fallback baseline alone — there is
    no learned tenant history yet on a first run, and seeding one from this same file would
    make the harness grade its own homework."""

    async def find_by_libelle(self, tenant_id, libelle_pattern) -> CategorizationPattern | None:
        return None

    async def upsert(self, pattern: CategorizationPattern) -> CategorizationPattern:
        return pattern


class _NullDecisionRepo:
    async def save(self, decision) -> None:
        return None

    async def get_by_ecriture(self, ecriture_id):
        return None


@dataclass
class _Row:
    libelle: str
    intitule: str
    montant: Decimal


def _read_rows(path: str) -> list[_Row]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    header = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
    col = {name: idx for idx, name in enumerate(header) if name is not None}
    if "Libellé de l'écriture" not in col or "Intitulé" not in col:
        raise SystemExit(
            f"Expected columns 'Libellé de l'écriture' and 'Intitulé' in the sheet header, "
            f"found: {list(col)}"
        )
    debit_idx = col.get("Débit")
    rows: list[_Row] = []
    for raw in sheet.iter_rows(min_row=2, values_only=True):
        libelle = raw[col["Libellé de l'écriture"]]
        intitule = raw[col["Intitulé"]]
        if not libelle or not intitule:
            continue
        montant = Decimal("0")
        if debit_idx is not None and raw[debit_idx]:
            try:
                montant = Decimal(str(raw[debit_idx]))
            except InvalidOperation:
                montant = Decimal("0")
        rows.append(_Row(libelle=str(libelle), intitule=str(intitule), montant=montant))
    return rows


async def _run(path: str) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            retriever = await RapidFuzzAccountRetriever.load(session)
    libelle_by_code = {c.code: c.libelle for c in retriever.comptes}

    use_case = CategorizeEcriture(
        pattern_repo=_NullPatternRepo(),
        account_retriever=retriever,
        decision_repo=_NullDecisionRepo(),
    )

    rows = _read_rows(path)
    plausible = 0
    escalated = 0
    print(f"{'libellé écriture':<40} | {'intitulé réel':<30} | {'compte prédit':<14} | {'conf.':<6} | statut | match?")
    print("-" * 120)
    for row in rows:
        ecriture = EcritureACategoriser(
            id=uuid4(), libelle=row.libelle, montant=row.montant, tiers=row.libelle, date=date.today(),
        )
        decision = await use_case.execute(tenant_id=uuid4(), ecriture=ecriture)
        predicted_libelle = libelle_by_code.get(decision.compte_code, "")
        score = fuzz.token_set_ratio(row.intitule, predicted_libelle) if predicted_libelle else 0.0
        is_plausible = score >= _PLAUSIBLE_MATCH_THRESHOLD
        plausible += int(is_plausible)
        escalated += int(decision.statut.value == "pending_review")
        print(
            f"{row.libelle[:40]:<40} | {row.intitule[:30]:<30} | {decision.compte_code:<14} | "
            f"{decision.confidence:<6.2f} | {decision.statut.value:<14} | {'oui' if is_plausible else 'non'}"
        )

    total = len(rows)
    print("-" * 120)
    print(f"Total lignes évaluées : {total}")
    if total:
        print(f"Match plausible (proxy heuristique) : {plausible}/{total} ({100 * plausible / total:.1f}%)")
        print(f"Escaladées en Human Review : {escalated}/{total} ({100 * escalated / total:.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xlsx_path", help="Path to a local 'Edition Journaux' export (never committed)")
    args = parser.parse_args()
    asyncio.run(_run(args.xlsx_path))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run it against the real local export**

```bash
docker compose up -d postgres
uv run alembic upgrade head
uv run python scripts/eval_categorization.py "$HOME/Downloads/Planet Edition provisoire des journaux du 01-01-2024 au 31-12-2024 (1).xlsx"
```

Expected: a printed table plus a summary with total rows, plausible-match percentage, and
Human Review escalation percentage. There is no fixed pass/fail threshold — read the per-row
table to judge whether phase-1 rapidfuzz is a good enough baseline, and use the numbers to
calibrate `min_occurrence_threshold` / `confidence_threshold` before deciding whether the phase-2
hybrid RAG brick is worth building next.

- [ ] **Step 4: Commit**

```bash
git add scripts/eval_categorization.py pyproject.toml uv.lock
git commit -m "feat(eval): add local evaluation harness for PCG categorization (spec Niveau 4)"
```

---

## Final check

```bash
uv run pytest -v -m "not integration"   # fast: domain + application (Tasks 1-6)
uv run pytest -v -m integration         # slow: infra + API (Tasks 7-11, requires Docker)
uv run ruff check src/ tests/ scripts/eval_categorization.py
```

All tasks complete. The PCG categorization brick (phase 1) is done:
- Clean Architecture layering (domain / application / infrastructure / interface), matching
  `tenancy` and `rapprochement`
- Tenant-pattern-first categorization with a rapidfuzz fallback over a seeded PCG reference table,
  behind a swappable `AccountRetriever` port
- Human-in-the-loop below the 85% confidence threshold; only human validation writes to the
  pattern table, preventing self-reinforcing errors
- Two endpoints: `POST /categorization/categorize`, `POST /categorization/validate`
- A local evaluation harness against real historical data to calibrate thresholds
- Next brick (separate spec + plan, not started here): hybrid RAG (Qdrant + BM25 + reranking)
  replacing `RapidFuzzAccountRetriever` behind the same `AccountRetriever` port, once the harness
  shows fuzzy matching alone isn't precise enough — see spec §"Lacunes connues"
