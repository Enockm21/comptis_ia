from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.rapprochement.use_cases import RunReconciliation, RunReconciliationRequest
from comptis.domain.rapprochement.entities import ReconciliationReport
from comptis.infrastructure.agents.rapprochement.graph import build_reconciliation_graph
from comptis.infrastructure.agents.rapprochement.llm_arbiter import LLMArbiter
from comptis.infrastructure.db.reconciliation_patterns import SQLAlchemyReconciliationPatternRepository
from comptis.interface.api.dependencies import get_db_session, require_api_key
from comptis.interface.api.rapprochement.schemas import (
    ConflictSchema,
    MatchSchema,
    ReportResponse,
    ResolveRequest,
    RunRequest,
    RunResponse,
    TransactionSchema,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

# In-memory store for run results (MVP — replace with Postgres checkpointer in production)
_runs: dict[str, dict] = {}


def _build_fake_mcp():
    """Placeholder MCP client — returns empty lists. Replace with real MCP client."""
    from comptis.application.rapprochement.ports import McpClient
    from datetime import date as _date
    from comptis.domain.rapprochement.entities import Transaction, Facture

    class _FakeMcp:
        async def list_transactions(self, statut=None, date_debut=None, date_fin=None):
            return []
        async def get_transaction(self, id): ...
        async def list_factures(self, statut=None, date_debut=None, date_fin=None):
            return []
        async def get_facture(self, id): ...
        async def mark_rapprochement(self, facture_id, transaction_id, statut): ...

    return _FakeMcp()


@router.post("/run", response_model=RunResponse, status_code=202)
async def run_reconciliation(
    body: RunRequest,
    org_id: uuid.UUID = Depends(require_api_key),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    memory = SQLAlchemyReconciliationPatternRepository(session)
    mcp_client = _build_fake_mcp()
    use_case = RunReconciliation(mcp_client=mcp_client, memory=memory)
    request = RunReconciliationRequest(
        tenant_id=body.tenant_id,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
    )
    date_debut, date_fin = use_case.resolve_window(request)

    run_id = str(uuid.uuid4())
    graph = build_reconciliation_graph(mcp_client, memory)
    initial_state = {
        "tenant_id": body.tenant_id,
        "date_debut": date_debut,
        "date_fin": date_fin,
        "transactions": [],
        "factures": [],
        "matches": [],
        "pending_review": [],
        "unmatched": [],
        "report": None,
    }
    result = await graph.ainvoke(initial_state)
    _runs[run_id] = result
    return RunResponse(
        run_id=run_id,
        tenant_id=body.tenant_id,
        date_debut=date_debut,
        date_fin=date_fin,
    )


@router.get("/run/{run_id}/conflicts", response_model=list[ConflictSchema])
async def get_conflicts(run_id: str) -> list[ConflictSchema]:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return [
        ConflictSchema(
            transaction=TransactionSchema(
                id=c.transaction.id,
                montant=c.transaction.montant,
                date=c.transaction.date,
                libelle=c.transaction.libelle,
            ),
            raison=c.raison,
            composite_score=c.composite_score,
        )
        for c in run.get("pending_review", [])
    ]


@router.get("/run/{run_id}/report", response_model=ReportResponse)
async def get_report(run_id: str) -> ReportResponse:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    report = run.get("report")
    if report is None:
        raise HTTPException(status_code=404, detail="Report not yet available")
    return ReportResponse(
        tenant_id=report.tenant_id,
        date_debut=report.date_debut,
        date_fin=report.date_fin,
        total_transactions=report.total_transactions,
        total_rapprochees=report.total_rapprochees,
        total_non_rapprochees=report.total_non_rapprochees,
        total_ecarts=report.total_ecarts,
        matches=[
            MatchSchema(
                facture_id=m.facture_id,
                transaction_id=m.transaction_id,
                confidence=m.confidence,
                ecart_montant=m.ecart_montant,
                statut=m.statut,
            )
            for m in report.matches
        ],
        unmatched=[
            TransactionSchema(id=t.id, montant=t.montant, date=t.date, libelle=t.libelle)
            for t in report.unmatched
        ],
    )
