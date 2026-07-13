from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from comptis.application.rapprochement.ports import McpClient, ReconciliationMemory
from comptis.domain.rapprochement.entities import ReconciliationReport

RECONCILIATION_WINDOW_DAYS_DEFAULT = 7
RECONCILIATION_WINDOW_MAX_DAYS = 90


@dataclass
class RunReconciliationRequest:
    tenant_id: UUID
    date_debut: date | None = None
    date_fin: date | None = None


@dataclass
class RunReconciliationResult:
    run_id: str
    tenant_id: UUID
    date_debut: date
    date_fin: date


class RunReconciliation:
    """Validates the request window and hands off to the LangGraph graph."""

    def __init__(self, mcp_client: McpClient, memory: ReconciliationMemory) -> None:
        self._mcp_client = mcp_client
        self._memory = memory

    def resolve_window(self, request: RunReconciliationRequest) -> tuple[date, date]:
        today = date.today()
        date_fin = request.date_fin or today
        date_debut = request.date_debut or (date_fin - timedelta(days=RECONCILIATION_WINDOW_DAYS_DEFAULT))
        span = (date_fin - date_debut).days
        if span > RECONCILIATION_WINDOW_MAX_DAYS:
            date_debut = date_fin - timedelta(days=RECONCILIATION_WINDOW_MAX_DAYS)
        return date_debut, date_fin
