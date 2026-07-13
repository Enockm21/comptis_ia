from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from comptis.domain.rapprochement.value_objects import (
    ConflictRaison,
    MatchStatut,
    RapprochementStatut,
)


@dataclass
class Facture:
    id: str
    montant: Decimal
    date: date
    fournisseur: str
    statut_rapprochement: RapprochementStatut
    transaction_id: str | None = None


@dataclass
class Transaction:
    id: str
    montant: Decimal
    date: date
    libelle: str
    facture_id: str | None = None


@dataclass
class Match:
    facture_id: str
    transaction_id: str
    confidence: float
    ecart_montant: Decimal
    statut: MatchStatut


@dataclass
class Conflict:
    transaction: Transaction
    facture: Facture | None
    raison: ConflictRaison
    composite_score: float


@dataclass
class ReconciliationPattern:
    tenant_id: UUID
    libelle_pattern: str
    fournisseur: str
    montant_approx: Decimal
    occurrence_count: int
    last_seen_at: datetime
    id: UUID = field(default_factory=uuid4)


@dataclass
class ReconciliationReport:
    tenant_id: UUID
    date_debut: date
    date_fin: date
    total_transactions: int
    total_rapprochees: int
    total_non_rapprochees: int
    total_ecarts: int
    matches: list[Match]
    unmatched: list[Transaction]
