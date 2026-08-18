from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class TVALine:
    taux: Decimal
    base_ht: Decimal
    montant_tva: Decimal
    nb_factures: int


@dataclass
class TVASummary:
    tva_collectee: Decimal
    tva_deductible: Decimal
    lignes_collectee: list[TVALine]
    lignes_deductible: list[TVALine]

    @property
    def tva_nette(self) -> Decimal:
        return self.tva_collectee - self.tva_deductible

    @property
    def est_credit(self) -> bool:
        return self.tva_nette < Decimal("0")


@dataclass
class TVADeclaration:
    tenant_id: UUID
    date_debut: date
    date_fin: date
    tva_collectee: Decimal
    tva_deductible: Decimal
    tva_nette: Decimal
    lignes: list[dict]  # serialized TVALine list
    statut: str = "brouillon"  # brouillon | deposee | payee
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.utcnow())
    deposee_le: datetime | None = None
    payee_le: datetime | None = None
