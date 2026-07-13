from __future__ import annotations

from langgraph.types import interrupt

from comptis.infrastructure.agents.rapprochement.state import ReconciliationState


async def human_review(state: ReconciliationState) -> dict:
    """Interrupt here for human decisions. Resumed with resolved conflicts."""
    if not state.get("pending_review"):
        return {}
    # Suspend — human operator reviews via POST /reconciliation/{run_id}/resolve
    decision = interrupt({"pending_review": state["pending_review"]})
    return {"pending_review": []}
