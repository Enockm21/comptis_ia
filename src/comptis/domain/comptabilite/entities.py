from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from .value_objects import StatutEcriture


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class CompteComptable:
    tenant_id: UUID
    numero: str
    libelle: str
    classe: int
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Ecriture:
    tenant_id: UUID
    transaction_id: str
    facture_id: str
    montant: Decimal
    date: date_
    compte_id: UUID | None = None
    statut: StatutEcriture = StatutEcriture.A_CATEGORISER
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
