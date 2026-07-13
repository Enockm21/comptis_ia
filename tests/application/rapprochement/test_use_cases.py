from datetime import date, timedelta
from uuid import uuid4

import pytest

from comptis.application.rapprochement.use_cases import (
    RECONCILIATION_WINDOW_MAX_DAYS,
    RunReconciliation,
    RunReconciliationRequest,
)


class _FakeMcp:
    async def list_transactions(self, **kw): return []
    async def get_transaction(self, id): ...
    async def list_factures(self, **kw): return []
    async def get_facture(self, id): ...
    async def mark_rapprochement(self, **kw): ...


class _FakeMemory:
    async def find_by_libelle(self, tenant_id, libelle_pattern): return None
    async def upsert(self, pattern): return pattern


def _use_case():
    return RunReconciliation(mcp_client=_FakeMcp(), memory=_FakeMemory())


def test_default_window_is_7_days():
    uc = _use_case()
    today = date.today()
    req = RunReconciliationRequest(tenant_id=uuid4())
    debut, fin = uc.resolve_window(req)
    assert fin == today
    assert (fin - debut).days == 7


def test_explicit_window_respected():
    uc = _use_case()
    debut_in = date(2026, 1, 1)
    fin_in = date(2026, 1, 10)
    req = RunReconciliationRequest(tenant_id=uuid4(), date_debut=debut_in, date_fin=fin_in)
    debut, fin = uc.resolve_window(req)
    assert debut == debut_in
    assert fin == fin_in


def test_window_capped_at_max():
    uc = _use_case()
    fin = date(2026, 6, 1)
    debut = fin - timedelta(days=200)
    req = RunReconciliationRequest(tenant_id=uuid4(), date_debut=debut, date_fin=fin)
    resolved_debut, resolved_fin = uc.resolve_window(req)
    assert (resolved_fin - resolved_debut).days == RECONCILIATION_WINDOW_MAX_DAYS


def test_custom_fin_without_debut():
    uc = _use_case()
    fin = date(2026, 3, 15)
    req = RunReconciliationRequest(tenant_id=uuid4(), date_fin=fin)
    debut, resolved_fin = uc.resolve_window(req)
    assert resolved_fin == fin
    assert (resolved_fin - debut).days == 7
