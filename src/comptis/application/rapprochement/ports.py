from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from comptis.domain.rapprochement.entities import (
    Facture,
    ReconciliationPattern,
    ReconciliationReport,
    Transaction,
)


class McpClient(Protocol):
    """Read/write access to PNiCompta via MCP."""

    async def list_transactions(
        self,
        statut: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[Transaction]: ...

    async def get_transaction(self, id: str) -> Transaction: ...

    async def list_factures(
        self,
        statut: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[Facture]: ...

    async def get_facture(self, id: str) -> Facture: ...

    async def mark_rapprochement(
        self,
        facture_id: str,
        transaction_id: str,
        statut: str,
    ) -> None: ...


class ReconciliationMemory(Protocol):
    """Pattern memory store."""

    async def find_by_libelle(
        self, tenant_id: UUID, libelle_pattern: str
    ) -> ReconciliationPattern | None: ...

    async def upsert(self, pattern: ReconciliationPattern) -> ReconciliationPattern: ...


class ReconciliationReporter(Protocol):
    """Build and persist the reconciliation report."""

    async def build(
        self,
        tenant_id: UUID,
        date_debut: date,
        date_fin: date,
        matches: list,
        unmatched: list[Transaction],
    ) -> ReconciliationReport: ...
