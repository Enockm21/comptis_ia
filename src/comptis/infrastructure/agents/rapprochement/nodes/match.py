from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

from comptis.application.rapprochement.ports import McpClient, ReconciliationMemory
from comptis.domain.rapprochement.entities import (
    Conflict,
    Match,
    ReconciliationPattern,
    Transaction,
)
from comptis.infrastructure.agents.rapprochement.llm_arbiter import LLMArbiter
from comptis.infrastructure.agents.rapprochement.scorer import (
    compute_composite_score,
    prefilter_candidates,
)
from comptis.infrastructure.agents.rapprochement.state import ReconciliationState

CONFIDENCE_THRESHOLD = float(os.environ.get("RECONCILIATION_CONFIDENCE_THRESHOLD", "0.85"))
LLM_LOWER_BOUND = float(os.environ.get("RECONCILIATION_LLM_LOWER_BOUND", "0.50"))
PATTERN_MIN_OCCURRENCES = int(os.environ.get("PATTERN_MIN_OCCURRENCES", "3"))


def make_match_node(
    mcp_client: McpClient,
    memory: ReconciliationMemory,
    arbiter: LLMArbiter,
):
    async def match(state: ReconciliationState) -> dict:
        tenant_id = state["tenant_id"]
        transactions = list(state["transactions"])
        factures = list(state["factures"])
        matches = list(state.get("matches", []))
        pending_review = list(state.get("pending_review", []))
        unmatched = list(state.get("unmatched", []))

        # Track matched facture IDs to avoid double-matching
        matched_facture_ids = {m.facture_id for m in matches}

        for txn in transactions:
            libelle_norm = txn.libelle.upper().strip()

            # 1. Memory lookup
            known_pattern = await memory.find_by_libelle(tenant_id, libelle_norm)
            if known_pattern and known_pattern.occurrence_count >= PATTERN_MIN_OCCURRENCES:
                # Find best matching facture for this pattern
                candidates = prefilter_candidates(
                    txn,
                    [f for f in factures if f.id not in matched_facture_ids],
                )
                if candidates:
                    best = max(candidates, key=lambda f: compute_composite_score(txn, f))
                    score = compute_composite_score(txn, best)
                    # Boost: if pattern known, use threshold directly
                    if score >= CONFIDENCE_THRESHOLD:
                        ecart = abs(txn.montant - best.montant)
                        statut = "confirme" if ecart == Decimal("0") else "ecart"
                        m = Match(
                            facture_id=best.id,
                            transaction_id=txn.id,
                            confidence=score,
                            ecart_montant=ecart,
                            statut=statut,
                        )
                        matches.append(m)
                        matched_facture_ids.add(best.id)
                        await mcp_client.mark_rapprochement(best.id, txn.id, statut)
                        # Upsert pattern to reinforce
                        pattern = ReconciliationPattern(
                            tenant_id=tenant_id,
                            libelle_pattern=libelle_norm,
                            fournisseur=best.fournisseur,
                            montant_approx=txn.montant,
                            occurrence_count=1,
                            last_seen_at=datetime.now(tz=timezone.utc),
                        )
                        await memory.upsert(pattern)
                        continue

            # 2. Pre-filter candidates
            candidates = prefilter_candidates(
                txn,
                [f for f in factures if f.id not in matched_facture_ids],
            )

            if not candidates:
                unmatched.append(txn)
                continue

            # 3. Score all candidates, pick best
            scored = [(f, compute_composite_score(txn, f)) for f in candidates]
            best_facture, best_score = max(scored, key=lambda x: x[1])

            if best_score >= CONFIDENCE_THRESHOLD:
                ecart = abs(txn.montant - best_facture.montant)
                statut = "confirme" if ecart == Decimal("0") else "ecart"
                m = Match(
                    facture_id=best_facture.id,
                    transaction_id=txn.id,
                    confidence=best_score,
                    ecart_montant=ecart,
                    statut=statut,
                )
                matches.append(m)
                matched_facture_ids.add(best_facture.id)
                await mcp_client.mark_rapprochement(best_facture.id, txn.id, statut)
                # Upsert pattern
                pattern = ReconciliationPattern(
                    tenant_id=tenant_id,
                    libelle_pattern=libelle_norm,
                    fournisseur=best_facture.fournisseur,
                    montant_approx=txn.montant,
                    occurrence_count=1,
                    last_seen_at=datetime.now(tz=timezone.utc),
                )
                await memory.upsert(pattern)

            elif best_score >= LLM_LOWER_BOUND:
                # LLM gray zone
                llm_confidence = await arbiter.judge(txn, best_facture)
                if llm_confidence >= CONFIDENCE_THRESHOLD:
                    ecart = abs(txn.montant - best_facture.montant)
                    statut = "confirme" if ecart == Decimal("0") else "ecart"
                    m = Match(
                        facture_id=best_facture.id,
                        transaction_id=txn.id,
                        confidence=llm_confidence,
                        ecart_montant=ecart,
                        statut=statut,
                    )
                    matches.append(m)
                    matched_facture_ids.add(best_facture.id)
                    await mcp_client.mark_rapprochement(best_facture.id, txn.id, statut)
                else:
                    conflict = Conflict(
                        transaction=txn,
                        facture=best_facture,
                        raison="confidence_insuffisante",
                        composite_score=best_score,
                    )
                    pending_review.append(conflict)
            else:
                unmatched.append(txn)

        return {
            "matches": matches,
            "pending_review": pending_review,
            "unmatched": unmatched,
        }

    return match
