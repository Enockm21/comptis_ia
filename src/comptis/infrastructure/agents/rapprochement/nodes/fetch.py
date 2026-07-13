from __future__ import annotations

import os
from datetime import date, timedelta

from comptis.application.rapprochement.ports import McpClient, ReconciliationMemory
from comptis.infrastructure.agents.rapprochement.state import ReconciliationState

RECONCILIATION_WINDOW_DAYS = int(os.environ.get("RECONCILIATION_WINDOW_DAYS", "7"))


def make_fetch_node(mcp_client: McpClient, memory: ReconciliationMemory):
    async def fetch(state: ReconciliationState) -> dict:
        tenant_id = state["tenant_id"]
        date_debut = state["date_debut"]
        date_fin = state["date_fin"]

        # Bootstrap memory from already-reconciled transactions (one-time per run)
        reconciled_txns = await mcp_client.list_transactions(statut="rapprochee")
        reconciled_factures = await mcp_client.list_factures(statut="rapprochee")

        # Upsert patterns from existing reconciliations
        from datetime import datetime, timezone
        from comptis.domain.rapprochement.entities import ReconciliationPattern
        for txn in reconciled_txns:
            # Find matching facture by facture_id
            matching = [f for f in reconciled_factures if f.id == txn.facture_id]
            if matching:
                f = matching[0]
                pattern = ReconciliationPattern(
                    tenant_id=tenant_id,
                    libelle_pattern=txn.libelle.upper().strip(),
                    fournisseur=f.fournisseur,
                    montant_approx=txn.montant,
                    occurrence_count=1,
                    last_seen_at=datetime.now(tz=timezone.utc),
                )
                await memory.upsert(pattern)

        # Load current window
        transactions = await mcp_client.list_transactions(
            statut="non_rapprochee",
            date_debut=date_debut,
            date_fin=date_fin,
        )
        factures = await mcp_client.list_factures(
            statut="non_rapprochee",
            date_debut=date_debut,
            date_fin=date_fin,
        )

        return {
            "transactions": transactions,
            "factures": factures,
            "matches": [],
            "pending_review": [],
            "unmatched": [],
        }

    return fetch
