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
