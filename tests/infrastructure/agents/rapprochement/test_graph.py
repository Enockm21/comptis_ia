from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from comptis.domain.rapprochement.entities import Facture, ReconciliationPattern, Transaction
from comptis.infrastructure.agents.rapprochement.graph import build_reconciliation_graph
from comptis.infrastructure.agents.rapprochement.llm_arbiter import LLMArbiter


class FakeMcp:
    def __init__(self, transactions=None, factures=None):
        self._transactions = transactions or []
        self._factures = factures or []
        self.marked = []

    async def list_transactions(self, statut=None, date_debut=None, date_fin=None):
        if statut == "rapprochee":
            return []
        return self._transactions

    async def get_transaction(self, id): ...

    async def list_factures(self, statut=None, date_debut=None, date_fin=None):
        if statut == "rapprochee":
            return []
        return self._factures

    async def get_facture(self, id): ...

    async def mark_rapprochement(self, facture_id, transaction_id, statut):
        self.marked.append((facture_id, transaction_id, statut))


class FakeMemory:
    def __init__(self):
        self._store = {}

    async def find_by_libelle(self, tenant_id, libelle_pattern):
        return self._store.get((str(tenant_id), libelle_pattern))

    async def upsert(self, pattern):
        key = (str(pattern.tenant_id), pattern.libelle_pattern)
        existing = self._store.get(key)
        if existing:
            from dataclasses import replace
            pattern = replace(pattern, occurrence_count=existing.occurrence_count + 1)
        self._store[key] = pattern
        return pattern


class FakeArbiter:
    def __init__(self, confidence=0.0):
        self._confidence = confidence

    async def judge(self, transaction, facture):
        return self._confidence


@pytest.mark.asyncio
async def test_direct_match_high_score():
    tenant_id = uuid4()
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC SARL FACTURE")
    f = Facture(id="f1", montant=Decimal("100.00"), date=date(2026, 1, 15),
                fournisseur="ABC SARL", statut_rapprochement="non_rapprochee")

    mcp = FakeMcp(transactions=[t], factures=[f])
    memory = FakeMemory()
    arbiter = FakeArbiter(confidence=0.0)

    graph = build_reconciliation_graph(mcp, memory, arbiter)
    initial_state = {
        "tenant_id": tenant_id,
        "date_debut": date(2026, 1, 1),
        "date_fin": date(2026, 1, 31),
        "transactions": [],
        "factures": [],
        "matches": [],
        "pending_review": [],
        "unmatched": [],
        "report": None,
    }
    result = await graph.ainvoke(initial_state)

    # Should have a report (no pending_review so no interrupt)
    assert result["report"] is not None
    assert result["report"].total_rapprochees == 1


@pytest.mark.asyncio
async def test_unmatched_when_no_candidates():
    tenant_id = uuid4()
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="UNKNOWN")
    # Facture with very different amount — won't pass prefilter
    f = Facture(id="f1", montant=Decimal("500.00"), date=date(2026, 1, 15),
                fournisseur="AUTRE", statut_rapprochement="non_rapprochee")

    mcp = FakeMcp(transactions=[t], factures=[f])
    memory = FakeMemory()
    arbiter = FakeArbiter(confidence=0.0)

    graph = build_reconciliation_graph(mcp, memory, arbiter)
    initial_state = {
        "tenant_id": tenant_id,
        "date_debut": date(2026, 1, 1),
        "date_fin": date(2026, 1, 31),
        "transactions": [],
        "factures": [],
        "matches": [],
        "pending_review": [],
        "unmatched": [],
        "report": None,
    }
    result = await graph.ainvoke(initial_state)
    assert result["report"].total_non_rapprochees == 1
    assert result["report"].total_rapprochees == 0


@pytest.mark.asyncio
async def test_report_totals_correct():
    tenant_id = uuid4()
    # t1 — direct match, t2 — unmatched (no candidates)
    t1 = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC SARL")
    t2 = Transaction(id="t2", montant=Decimal("999.99"), date=date(2026, 1, 15), libelle="MYSTERY")
    f1 = Facture(id="f1", montant=Decimal("100.00"), date=date(2026, 1, 15),
                 fournisseur="ABC SARL", statut_rapprochement="non_rapprochee")

    mcp = FakeMcp(transactions=[t1, t2], factures=[f1])
    memory = FakeMemory()
    arbiter = FakeArbiter(confidence=0.0)

    graph = build_reconciliation_graph(mcp, memory, arbiter)
    initial_state = {
        "tenant_id": tenant_id,
        "date_debut": date(2026, 1, 1),
        "date_fin": date(2026, 1, 31),
        "transactions": [],
        "factures": [],
        "matches": [],
        "pending_review": [],
        "unmatched": [],
        "report": None,
    }
    result = await graph.ainvoke(initial_state)
    r = result["report"]
    assert r.total_transactions == 2
    assert r.total_rapprochees == 1
    assert r.total_non_rapprochees == 1
