from __future__ import annotations

from datetime import date
from typing import TypedDict
from uuid import UUID

from comptis.domain.rapprochement.entities import (
    Conflict,
    Facture,
    Match,
    ReconciliationReport,
    Transaction,
)


class ReconciliationState(TypedDict):
    tenant_id: UUID
    date_debut: date
    date_fin: date
    transactions: list[Transaction]
    factures: list[Facture]
    matches: list[Match]
    pending_review: list[Conflict]
    unmatched: list[Transaction]
    report: ReconciliationReport | None
