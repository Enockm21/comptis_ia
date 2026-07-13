from __future__ import annotations

from comptis.domain.rapprochement.entities import ReconciliationReport
from comptis.infrastructure.agents.rapprochement.state import ReconciliationState


async def report(state: ReconciliationState) -> dict:
    matches = state.get("matches", [])
    unmatched = state.get("unmatched", [])

    r = ReconciliationReport(
        tenant_id=state["tenant_id"],
        date_debut=state["date_debut"],
        date_fin=state["date_fin"],
        total_transactions=len(matches) + len(unmatched),
        total_rapprochees=sum(1 for m in matches if m.statut == "confirme"),
        total_non_rapprochees=len(unmatched),
        total_ecarts=sum(1 for m in matches if m.statut == "ecart"),
        matches=matches,
        unmatched=unmatched,
    )
    return {"report": r}
