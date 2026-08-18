from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.comptabilite.use_cases import CreerEcritureDepuisMatch
from comptis.application.rapprochement.use_cases import RunReconciliation, RunReconciliationRequest
from comptis.domain.rapprochement.entities import ReconciliationReport
from comptis.infrastructure.agents.rapprochement.graph import build_reconciliation_graph
from comptis.infrastructure.agents.rapprochement.llm_arbiter import LLMArbiter
from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyEcritureRepository
from comptis.infrastructure.db.reconciliation_patterns import SQLAlchemyReconciliationPatternRepository
from comptis.infrastructure.db.reconciliation_run_repository import SQLAlchemyReconciliationRunRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.infrastructure.mcp.client_factory import build_mcp_client_for_org
from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient
from comptis.infrastructure.mcp.pnicompta_mcp_client import PniComptaMcpClient
from comptis.interface.api.dependencies import get_db_session, require_user
from comptis.interface.api.rapprochement.schemas import (
    ConflictSchema,
    FactureSchema,
    MatchSchema,
    ReportResponse,
    ResolveRequest,
    RunHistoryItem,
    RunRequest,
    RunResponse,
    TransactionSchema,
)

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

# In-memory store for run results (MVP — replace with Postgres checkpointer in production)
_runs: dict[str, dict] = {}


async def _require_tenant_access(tenant_id, session: AsyncSession, not_found_detail: str = "Tenant not found"):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return tenant


@router.post("/run", response_model=RunResponse, status_code=202)
async def run_reconciliation(
    body: RunRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    tenant = await _require_tenant_access(body.tenant_id, session)
    org_id = tenant.organization_id
    await set_tenant_context(
        session, organization_id=org_id, tenant_id=body.tenant_id, user_id=user_id
    )

    memory = SQLAlchemyReconciliationPatternRepository(session)
    ecriture_repo = SQLAlchemyEcritureRepository(session)
    mcp_client = await build_mcp_client_for_org(org_id, session)
    use_case = RunReconciliation(mcp_client=mcp_client, memory=memory)
    request = RunReconciliationRequest(
        tenant_id=body.tenant_id,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
    )
    date_debut, date_fin = use_case.resolve_window(request)

    run_id = str(uuid.uuid4())
    graph = build_reconciliation_graph(mcp_client, memory, ecriture_repo)  # type: ignore[arg-type]
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

    # Persist run summary in DB
    matches = result.get("matches", [])
    unmatched = result.get("unmatched", [])
    pending = result.get("pending_review", [])
    total_ecarts = sum(1 for m in matches if m.statut == "ecart")
    total_rapprochees = sum(1 for m in matches if m.statut == "confirme") + total_ecarts
    total_non_rapprochees = len(unmatched)
    total_transactions = total_rapprochees + total_ecarts + total_non_rapprochees + len(pending)
    run_repo = SQLAlchemyReconciliationRunRepository(session)
    await run_repo.save(
        tenant_id=body.tenant_id,
        date_debut=date_debut,
        date_fin=date_fin,
        total_transactions=total_transactions,
        total_rapprochees=total_rapprochees,
        total_ecarts=total_ecarts,
        total_non_rapprochees=total_non_rapprochees,
        statut="en_cours" if pending else "termine",
    )

    return RunResponse(
        run_id=run_id,
        tenant_id=body.tenant_id,
        date_debut=date_debut,
        date_fin=date_fin,
    )


@router.post("/run/{run_id}/resolve", status_code=200)
async def resolve_conflict(
    run_id: str,
    body: ResolveRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _require_tenant_access(run["tenant_id"], session, not_found_detail="Run not found")
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(run["tenant_id"])
    org_id = tenant.organization_id
    await set_tenant_context(session, organization_id=org_id, tenant_id=run["tenant_id"], user_id=user_id)
    ecriture_repo = SQLAlchemyEcritureRepository(session)

    pending = list(run.get("pending_review", []))
    conflict = next((c for c in pending if c.transaction.id == body.conflict_id), None)
    if conflict is None:
        raise HTTPException(status_code=404, detail="Conflict not found")

    pending.remove(conflict)
    matches = list(run.get("matches", []))
    unmatched = list(run.get("unmatched", []))

    if body.decision == "confirmer" and conflict.facture is not None:
        from decimal import Decimal
        from comptis.domain.rapprochement.entities import Match
        ecart = abs(conflict.transaction.montant - conflict.facture.montant)
        matches.append(Match(
            facture_id=conflict.facture.id,
            transaction_id=conflict.transaction.id,
            confidence=conflict.composite_score,
            ecart_montant=ecart,
            statut="confirme",
        ))
        await CreerEcritureDepuisMatch(ecriture_repo).execute(
            tenant_id=run["tenant_id"],
            transaction_id=conflict.transaction.id,
            facture_id=conflict.facture.id,
            montant=abs(conflict.transaction.montant),
            date_=conflict.transaction.date,
        )
    elif body.decision == "ecart_accepte" and conflict.facture is not None:
        from decimal import Decimal
        from comptis.domain.rapprochement.entities import Match
        ecart = abs(conflict.transaction.montant - conflict.facture.montant)
        matches.append(Match(
            facture_id=conflict.facture.id,
            transaction_id=conflict.transaction.id,
            confidence=conflict.composite_score,
            ecart_montant=ecart,
            statut="ecart",
        ))
        await CreerEcritureDepuisMatch(ecriture_repo).execute(
            tenant_id=run["tenant_id"],
            transaction_id=conflict.transaction.id,
            facture_id=conflict.facture.id,
            montant=abs(conflict.transaction.montant),
            date_=conflict.transaction.date,
        )
    else:
        unmatched.append(conflict.transaction)

    run["pending_review"] = pending
    run["matches"] = matches
    run["unmatched"] = unmatched

    # Rebuild report once all conflicts resolved
    if not pending:
        from comptis.domain.rapprochement.entities import ReconciliationReport
        from uuid import UUID
        run["report"] = ReconciliationReport(
            tenant_id=run["tenant_id"],
            date_debut=run["date_debut"],
            date_fin=run["date_fin"],
            total_transactions=len(matches) + len(unmatched),
            total_rapprochees=sum(1 for m in matches if m.statut == "confirme"),
            total_non_rapprochees=len(unmatched),
            total_ecarts=sum(1 for m in matches if m.statut == "ecart"),
            matches=matches,
            unmatched=unmatched,
        )

    return {"status": "ok", "pending_remaining": len(pending)}


@router.get("/run/{run_id}/conflicts", response_model=list[ConflictSchema])
async def get_conflicts(
    run_id: str,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ConflictSchema]:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _require_tenant_access(run["tenant_id"], session, not_found_detail="Run not found")
    return [
        ConflictSchema(
            transaction=TransactionSchema(
                id=c.transaction.id,
                montant=c.transaction.montant,
                date=c.transaction.date,
                libelle=c.transaction.libelle,
            ),
            facture=FactureSchema(
                id=c.facture.id,
                montant=c.facture.montant,
                date=c.facture.date,
                fournisseur=c.facture.fournisseur,
            ) if c.facture is not None else None,
            raison=c.raison,
            composite_score=c.composite_score,
        )
        for c in run.get("pending_review", [])
    ]


@router.get("/run/{run_id}/report", response_model=ReportResponse)
async def get_report(
    run_id: str,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _require_tenant_access(run["tenant_id"], session, not_found_detail="Run not found")
    report = run.get("report")
    if report is None:
        raise HTTPException(status_code=404, detail="Report not yet available")
    # Build lookup maps for enriching matches
    transactions_by_id = {t.id: t for t in run.get("transactions", [])}
    factures_by_id = {f.id: f for f in run.get("factures", [])}

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
                libelle=getattr(transactions_by_id.get(m.transaction_id), "libelle", ""),
                fournisseur=getattr(factures_by_id.get(m.facture_id), "fournisseur", ""),
            )
            for m in report.matches
        ],
        unmatched=[
            TransactionSchema(id=t.id, montant=t.montant, date=t.date, libelle=t.libelle)
            for t in report.unmatched
        ],
    )


@router.get("/history", response_model=list[RunHistoryItem])
async def list_run_history(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[RunHistoryItem]:
    tenant = await _require_tenant_access(tenant_id, session)
    await set_tenant_context(
        session, organization_id=tenant.organization_id, tenant_id=tenant_id, user_id=user_id
    )
    repo = SQLAlchemyReconciliationRunRepository(session)
    runs = await repo.list_by_tenant(tenant_id)
    return [
        RunHistoryItem(
            id=r.id,
            tenant_id=r.tenant_id,
            date_debut=r.date_debut,
            date_fin=r.date_fin,
            total_transactions=r.total_transactions,
            total_rapprochees=r.total_rapprochees,
            total_ecarts=r.total_ecarts,
            total_non_rapprochees=r.total_non_rapprochees,
            statut=r.statut,
            ran_at=r.ran_at,
        )
        for r in runs
    ]
