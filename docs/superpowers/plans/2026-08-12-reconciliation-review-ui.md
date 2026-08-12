# Reconciliation Review UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the human review UI for the reconciliation ("rapprochement") flow — login, trigger a run, review conflicts one at a time (with the candidate facture now visible), and see the final report — plus the backend fixes needed to make that flow usable and secure.

**Architecture:** Backend: migrate `/reconciliation` router from `require_api_key` to `require_user`, derive `org_id` from the chosen `tenant_id` instead of the auth dependency, add a tenant-ownership check (RLS-backed) on every endpoint that reads a run, expose the candidate `Facture` on `ConflictSchema`, add a new `/tenants` endpoint backed by a new `TenantRepository.list_visible()` method that relies on the existing `membership_access` RLS policy. Frontend: a `/login` page, a route guard, and a `/reconciliation` page that walks trigger → review → report as local React state (no new routes per step — nothing is persisted server-side to resume).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async (existing RLS), React 18 + TypeScript + Vite (existing), no new dependencies.

## Global Constraints

- Clean Architecture: domain ← application ← infrastructure ← interface. No layer imports from an outer layer.
- All async DB calls use `AsyncSession` from `app_engine` (comptis_app role, RLS enforced)
- `pytestmark = pytest.mark.asyncio(loop_scope="session")` on every interface test module using the session-scoped `client`/`admin_token` fixtures
- Integration tests marked `@pytest.mark.integration`, run via `arch -arm64 uv run pytest -v -m integration` on this machine (Rosetta shell mismatch — see prior session notes)
- Commit message format: `type(scope): description`
- Ruff line-length = 100
- Frontend: no test infra exists — verify manually in browser, don't introduce one
- Frontend: inline styles, no CSS modules — matches `AdminIntegrations.tsx` / `IntegrationForm.tsx`

---

## File Map

**New files:**
```
src/comptis/interface/api/tenancy/__init__.py
src/comptis/interface/api/tenancy/schemas.py
src/comptis/interface/api/tenancy/router.py

tests/interface/api/test_tenancy.py

frontend/src/pages/Login.tsx
frontend/src/pages/Reconciliation.tsx
frontend/src/components/ConflictReview.tsx
frontend/src/components/ReconciliationReport.tsx
frontend/src/lib/tenants.ts
frontend/src/lib/reconciliation.ts
```

**Modified files:**
```
src/comptis/application/tenancy/ports.py             → add TenantRepository.list_visible
src/comptis/infrastructure/db/repositories.py         → implement SQLAlchemyTenantRepository.list_visible
src/comptis/interface/api/rapprochement/schemas.py    → add FactureSchema, ConflictSchema.facture
src/comptis/interface/api/rapprochement/router.py     → require_user everywhere, tenant-ownership check
src/comptis/interface/api/main.py                     → register tenancy router
tests/infrastructure/db/tenancy/test_repositories.py  → test list_visible
tests/interface/api/conftest.py                       → expose admin_tenant_id fixture
tests/interface/api/test_rapprochement.py             → rewrite for require_user + facture + ownership
frontend/src/lib/auth.ts                              → add login()
frontend/src/App.tsx                                  → add /login, /reconciliation routes + guard
frontend/vite.config.ts                                → proxy /auth, /reconciliation, /tenants
```

---
## Task 1: Expose `admin_tenant_id` from the shared test fixture

**Files:**
- Modify: `tests/interface/api/conftest.py`

**Interfaces:**
- Produces: `admin_identity` fixture (dict: `token`, `user_id`, `org_id`, `tenant_id`, all `str`), `admin_token` (str, unchanged signature), `admin_tenant_id` (str, new)

The current `admin_token` fixture creates an org/tenant/membership internally but never exposes the `tenant_id` it generated — every later task needs it to seed/assert against a specific tenant. Refactor without changing `admin_token`'s existing type (`str`) so `test_auth.py` and `test_admin_integrations.py` keep working untouched.

- [ ] **Step 1: Replace the `admin_token` fixture with `admin_identity` + two thin wrappers**

In `tests/interface/api/conftest.py`, replace the existing `admin_token` fixture (the one that does the register/login/seed dance) with:

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_identity(client, admin_db_url) -> dict:
    """Register an admin user, seed org+tenant+membership, return the ids."""
    email = f"admin-{_uuid_module.uuid4()}@test.com"
    await client.post("/auth/register", json={"email": email, "password": "Test1234!"})
    resp = await client.post("/auth/login", json={"email": email, "password": "Test1234!"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    from comptis.infrastructure.auth.jwt import JWTTokenService
    payload = JWTTokenService().decode(token)
    user_id = payload["sub"]

    sync_engine = create_engine(admin_db_url)
    org_id = str(_uuid_module.uuid4())
    tenant_id = str(_uuid_module.uuid4())
    membership_id = str(_uuid_module.uuid4())
    with sync_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO organizations(id, name, type, created_at) "
            "VALUES (:id, :name, :type, NOW())"
        ), {"id": org_id, "name": "Test Org", "type": "company"})
        conn.execute(text(
            "INSERT INTO tenants(id, organization_id, name, created_at) "
            "VALUES (:id, :org_id, :name, NOW())"
        ), {"id": tenant_id, "org_id": org_id, "name": "Test Tenant"})
        conn.execute(text(
            "INSERT INTO memberships(id, user_id, tenant_id, role, created_at) "
            "VALUES (:id, :user_id, :tenant_id, :role, NOW())"
        ), {"id": membership_id, "user_id": user_id, "tenant_id": tenant_id, "role": "admin"})
    sync_engine.dispose()

    return {"token": token, "user_id": user_id, "org_id": org_id, "tenant_id": tenant_id}


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_token(admin_identity: dict) -> str:
    return admin_identity["token"]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_tenant_id(admin_identity: dict) -> str:
    return admin_identity["tenant_id"]
```

Leave the `user_token` fixture untouched — it deliberately has no membership, and Task 5's tests rely on that.

- [ ] **Step 2: Run the existing test files to confirm nothing broke**

```bash
arch -arm64 uv run pytest tests/interface/api/test_auth.py tests/interface/api/test_admin_integrations.py -v -m integration
```

Expected: same pass count as before this change (`admin_token` still resolves to a plain string).

- [ ] **Step 3: Commit**

```bash
git add tests/interface/api/conftest.py
git commit -m "test(interface): expose admin_tenant_id from shared admin fixture"
```

---

## Task 2: `TenantRepository.list_visible`

**Files:**
- Modify: `src/comptis/application/tenancy/ports.py`
- Modify: `src/comptis/infrastructure/db/repositories.py`
- Test: `tests/infrastructure/db/tenancy/test_repositories.py`

**Interfaces:**
- Produces: `TenantRepository.list_visible(session: AsyncSession) -> list[Tenant]` — relies entirely on RLS, no `WHERE` clause. Under a session where only `app.current_user_id` is set (no `app.current_organization_id`), only the `membership_access` policy can grant rows, so this returns exactly the tenants the current user has a membership on.

- [ ] **Step 1: Write the failing test**

Add to `tests/infrastructure/db/tenancy/test_repositories.py`:

```python
@pytest.mark.integration
async def test_list_visible_returns_only_tenants_with_membership(db_session):
    org_repo = SQLAlchemyOrganizationRepository(db_session)
    user_repo = SQLAlchemyUserRepository(db_session)
    tenant_repo = SQLAlchemyTenantRepository(db_session)
    membership_repo = SQLAlchemyMembershipRepository(db_session)

    org = Organization(name="Org Visible", type=OrgType.CABINET)
    await org_repo.save(org)
    user = User(email=f"user-{uuid4()}@test.fr")
    await user_repo.save(user)

    # org_access must be true to INSERT the tenants at all
    await set_tenant_context(db_session, organization_id=org.id, user_id=user.id)
    tenant_a = Tenant(organization_id=org.id, name="Client Visible")
    tenant_b = Tenant(organization_id=org.id, name="Client Invisible")
    await tenant_repo.save(tenant_a)
    await tenant_repo.save(tenant_b)
    membership = Membership(user_id=user.id, tenant_id=tenant_a.id, role=Role.ACCOUNTANT)
    await membership_repo.save(membership)

    # Neutralise org_access by pointing it at an org that owns nothing, so only
    # membership_access can grant visibility — this mirrors require_user, which
    # never sets app.current_organization_id at all.
    await set_tenant_context(db_session, organization_id=uuid4(), user_id=user.id)
    visible = await tenant_repo.list_visible(db_session)
    names = {t.name for t in visible}
    assert "Client Visible" in names
    assert "Client Invisible" not in names
```

- [ ] **Step 2: Run to see it fail**

```bash
arch -arm64 uv run pytest tests/infrastructure/db/tenancy/test_repositories.py::test_list_visible_returns_only_tenants_with_membership -v -m integration
```

Expected: `AttributeError: 'SQLAlchemyTenantRepository' object has no attribute 'list_visible'`

- [ ] **Step 3: Add `list_visible` to the port and the implementation**

In `src/comptis/application/tenancy/ports.py`, add to `TenantRepository`:

```python
class TenantRepository(Protocol):
    async def save(self, tenant: Tenant) -> None: ...
    async def get_by_id(self, id: UUID) -> Tenant | None: ...
    async def list_by_organization(self, org_id: UUID) -> list[Tenant]: ...
    async def list_visible(self, session) -> list[Tenant]: ...
```

In `src/comptis/infrastructure/db/repositories.py`, add to `SQLAlchemyTenantRepository`:

```python
    async def list_visible(self, session: AsyncSession) -> list[Tenant]:
        # No WHERE clause — RLS (membership_access) does the filtering under
        # a require_user session (app.current_organization_id unset).
        result = await session.execute(select(TenantModel))
        return [_tenant_to_domain(m) for m in result.scalars().all()]
```

- [ ] **Step 4: Run to see it pass**

```bash
arch -arm64 uv run pytest tests/infrastructure/db/tenancy/test_repositories.py -v -m integration
```

Expected: all tests in the file pass (4 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add src/comptis/application/tenancy/ports.py src/comptis/infrastructure/db/repositories.py tests/infrastructure/db/tenancy/test_repositories.py
git commit -m "feat(tenancy): add TenantRepository.list_visible relying on membership RLS"
```

---

## Task 3: `GET /tenants` endpoint

**Files:**
- Create: `src/comptis/interface/api/tenancy/__init__.py`
- Create: `src/comptis/interface/api/tenancy/schemas.py`
- Create: `src/comptis/interface/api/tenancy/router.py`
- Modify: `src/comptis/interface/api/main.py`
- Test: `tests/interface/api/test_tenancy.py`

**Interfaces:**
- Consumes: `require_user`, `get_db_session` from `comptis.interface.api.dependencies`; `SQLAlchemyTenantRepository.list_visible` from Task 2
- Produces: `router` (FastAPI `APIRouter`, no prefix, route `GET /tenants`), `TenantSchema` (`id: UUID`, `name: str`)

- [ ] **Step 1: Create `__init__.py`**

```bash
mkdir -p src/comptis/interface/api/tenancy
touch src/comptis/interface/api/tenancy/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/interface/api/test_tenancy.py`:

```python
import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_list_tenants_requires_auth(client):
    resp = await client.get("/tenants")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_list_tenants_returns_only_my_tenants(client, admin_token: str, admin_tenant_id: str):
    resp = await client.get("/tenants", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert admin_tenant_id in ids


@pytest.mark.integration
async def test_list_tenants_empty_for_user_without_membership(client, user_token: str):
    resp = await client.get("/tenants", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 3: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/interface/api/test_tenancy.py -v -m integration
```

Expected: `404` on all three (route doesn't exist yet).

- [ ] **Step 4: Implement `schemas.py`**

Create `src/comptis/interface/api/tenancy/schemas.py`:

```python
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TenantSchema(BaseModel):
    id: UUID
    name: str
```

- [ ] **Step 5: Implement `router.py`**

Create `src/comptis/interface/api/tenancy/router.py`:

```python
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.interface.api.dependencies import get_db_session, require_user
from comptis.interface.api.tenancy.schemas import TenantSchema

router = APIRouter(tags=["tenancy"])


@router.get("/tenants", response_model=list[TenantSchema])
async def list_my_tenants(
    user_id: UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantSchema]:
    repo = SQLAlchemyTenantRepository(session)
    tenants = await repo.list_visible(session)
    return [TenantSchema(id=t.id, name=t.name) for t in tenants]
```

- [ ] **Step 6: Register the router in `main.py`**

In `src/comptis/interface/api/main.py`, add the import alongside the others and register it:

```python
from comptis.interface.api.tenancy.router import router as tenancy_router
```

```python
app.include_router(tenancy_router)
```

- [ ] **Step 7: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/interface/api/test_tenancy.py -v -m integration
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add src/comptis/interface/api/tenancy/ src/comptis/interface/api/main.py tests/interface/api/test_tenancy.py
git commit -m "feat(interface): add GET /tenants endpoint"
```

---

## Task 4: `/reconciliation` router — `require_user`, tenant ownership, facture on conflicts

**Files:**
- Modify: `src/comptis/interface/api/rapprochement/schemas.py`
- Modify: `src/comptis/interface/api/rapprochement/router.py`
- Modify: `tests/interface/api/test_rapprochement.py` (full rewrite)

**Interfaces:**
- Consumes: `require_user` from `comptis.interface.api.dependencies`, `SQLAlchemyTenantRepository` from `comptis.infrastructure.db.repositories`, `admin_token`/`admin_tenant_id`/`user_token` from Task 1
- Produces: `FactureSchema` (`id: str`, `montant: Decimal`, `date: date`, `fournisseur: str`); `ConflictSchema.facture: FactureSchema | None`

This is Bloc 1 of the approved spec end to end: `POST /run` and `POST /run/{id}/resolve` move from `require_api_key` to `require_user`; `GET /run/{id}/conflicts` and `GET /run/{id}/report` gain `require_user` (they have no auth at all today); every endpoint that reads an existing run additionally checks the run's `tenant_id` is visible to the current user (same RLS `get_by_id` used everywhere else — `None` means "not accessible", answered with 404 so the run's existence isn't leaked to users without access).

- [ ] **Step 1: Write the failing tests (full rewrite of `tests/interface/api/test_rapprochement.py`)**

Replace the entire contents of `tests/interface/api/test_rapprochement.py` with:

```python
import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.domain.rapprochement.entities import Conflict, Facture, Transaction
from comptis.interface.api.rapprochement.router import _runs

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _seed_run(tenant_id: str, pending_review: list[Conflict]) -> str:
    run_id = str(uuid4())
    _runs[run_id] = {
        "tenant_id": tenant_id,
        "date_debut": date(2026, 1, 1),
        "date_fin": date(2026, 1, 31),
        "pending_review": pending_review,
        "matches": [],
        "unmatched": [],
        "report": None,
    }
    return run_id


@pytest.mark.integration
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.integration
async def test_run_reconciliation_requires_auth(client):
    resp = await client.post("/reconciliation/run", json={"tenant_id": str(uuid4())})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_run_reconciliation_rejects_unknown_tenant(client, admin_token: str):
    resp = await client.post(
        "/reconciliation/run",
        json={"tenant_id": str(uuid4())},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_get_conflicts_requires_auth(client):
    resp = await client.get("/reconciliation/run/nonexistent/conflicts")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_get_conflicts_includes_candidate_facture(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC SARL")
    facture = Facture(
        id="f1", montant=Decimal("105.00"), date=date(2026, 1, 15),
        fournisseur="ABC SARL", statut_rapprochement="non_rapprochee",
    )
    conflict = Conflict(transaction=transaction, facture=facture, raison="ecart_montant", composite_score=0.8)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/conflicts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["facture"]["fournisseur"] == "ABC SARL"
    assert body[0]["facture"]["montant"] == "105.00"
    assert body[0]["raison"] == "ecart_montant"


@pytest.mark.integration
async def test_get_conflicts_facture_null_when_no_candidate(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t2", montant=Decimal("50.00"), date=date(2026, 1, 15), libelle="MYSTERY")
    conflict = Conflict(transaction=transaction, facture=None, raison="confidence_insuffisante", composite_score=0.4)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/conflicts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["facture"] is None


@pytest.mark.integration
async def test_get_conflicts_rejects_run_of_inaccessible_tenant(client, admin_tenant_id: str, user_token: str):
    run_id = _seed_run(admin_tenant_id, [])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/conflicts",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_resolve_conflict_confirms_match_and_builds_report(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t3", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC SARL")
    facture = Facture(
        id="f3", montant=Decimal("100.00"), date=date(2026, 1, 15),
        fournisseur="ABC SARL", statut_rapprochement="non_rapprochee",
    )
    conflict = Conflict(transaction=transaction, facture=facture, raison="confidence_insuffisante", composite_score=0.7)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "t3", "decision": "confirmer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["pending_remaining"] == 0
    assert _runs[run_id]["report"] is not None
    assert _runs[run_id]["report"].total_rapprochees == 1


@pytest.mark.integration
async def test_resolve_conflict_rejects_run_of_inaccessible_tenant(client, admin_tenant_id: str, user_token: str):
    run_id = _seed_run(admin_tenant_id, [])

    resp = await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "whatever", "decision": "rejeter"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_get_report_requires_auth(client):
    resp = await client.get("/reconciliation/run/nonexistent/report")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_get_report_after_all_conflicts_resolved(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t4", montant=Decimal("80.00"), date=date(2026, 1, 15), libelle="XYZ")
    facture = Facture(
        id="f4", montant=Decimal("80.00"), date=date(2026, 1, 15),
        fournisseur="XYZ", statut_rapprochement="non_rapprochee",
    )
    conflict = Conflict(transaction=transaction, facture=facture, raison="ecart_montant", composite_score=0.6)
    run_id = _seed_run(admin_tenant_id, [conflict])
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "t4", "decision": "confirmer"},
        headers=headers,
    )
    resp = await client.get(f"/reconciliation/run/{run_id}/report", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_rapprochees"] == 1
    assert body["total_transactions"] == 1
```

- [ ] **Step 2: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/interface/api/test_rapprochement.py -v -m integration
```

Expected: the `requires_auth` tests fail (401 expected, currently no auth at all so they'd get other codes or pass through); the `facture` tests fail with a `KeyError`/`AttributeError` on `facture` (field doesn't exist yet).

- [ ] **Step 3: Add `FactureSchema` and `ConflictSchema.facture`**

In `src/comptis/interface/api/rapprochement/schemas.py`, add `FactureSchema` right after the imports and before `RunRequest`, then update `ConflictSchema`:

```python
class FactureSchema(BaseModel):
    id: str
    montant: Decimal
    date: date
    fournisseur: str
```

```python
class ConflictSchema(BaseModel):
    transaction: TransactionSchema
    facture: FactureSchema | None
    raison: str
    composite_score: float
```

- [ ] **Step 4: Migrate `router.py` to `require_user` with tenant-ownership checks**

In `src/comptis/interface/api/rapprochement/router.py`:

Replace the import of `require_api_key` with `require_user`, and add the tenant repository import:

```python
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.interface.api.dependencies import get_db_session, require_user
```

Also import `FactureSchema`:

```python
from comptis.interface.api.rapprochement.schemas import (
    ConflictSchema,
    FactureSchema,
    MatchSchema,
    ReportResponse,
    ResolveRequest,
    RunRequest,
    RunResponse,
    TransactionSchema,
)
```

Add a shared ownership-check helper right after `_build_mcp_client_for_org`:

```python
async def _require_tenant_access(tenant_id, session: AsyncSession):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant
```

Replace `run_reconciliation`'s signature and the start of its body — `org_id` no longer comes from the auth dependency, it's derived from the tenant:

```python
@router.post("/run", response_model=RunResponse, status_code=202)
async def run_reconciliation(
    body: RunRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> RunResponse:
    tenant = await _require_tenant_access(body.tenant_id, session)
    org_id = tenant.organization_id

    memory = SQLAlchemyReconciliationPatternRepository(session)
    mcp_client = await _build_mcp_client_for_org(org_id, session)
```

(the rest of the function body — `use_case`, `request`, `resolve_window`, graph invocation, `_runs[run_id] = result`, `return RunResponse(...)` — is unchanged)

Replace `resolve_conflict`'s signature (add `session`, swap the auth dependency, add the ownership check right after the "run not found" check):

```python
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
    await _require_tenant_access(run["tenant_id"], session)

    pending = list(run.get("pending_review", []))
```

(the rest of the function body is unchanged)

Replace `get_conflicts` entirely:

```python
@router.get("/run/{run_id}/conflicts", response_model=list[ConflictSchema])
async def get_conflicts(
    run_id: str,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ConflictSchema]:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _require_tenant_access(run["tenant_id"], session)
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
```

Replace `get_report`'s signature (add auth + ownership check, body unchanged below it):

```python
@router.get("/run/{run_id}/report", response_model=ReportResponse)
async def get_report(
    run_id: str,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> ReportResponse:
    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _require_tenant_access(run["tenant_id"], session)
    report = run.get("report")
```

- [ ] **Step 5: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/interface/api/test_rapprochement.py -v -m integration
```

Expected: all pass.

- [ ] **Step 6: Run the full non-integration and integration suites to confirm nothing else broke**

```bash
arch -arm64 uv run pytest -v -m "not integration"
arch -arm64 uv run pytest -v -m integration
```

Expected: same green state as before this task, plus the new passes.

- [ ] **Step 7: Commit**

```bash
git add src/comptis/interface/api/rapprochement/schemas.py src/comptis/interface/api/rapprochement/router.py tests/interface/api/test_rapprochement.py
git commit -m "feat(reconciliation): require_user + tenant ownership checks, expose candidate facture"
```

---

## Task 5: Frontend API client — auth login, tenants, reconciliation

**Files:**
- Modify: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/tenants.ts`
- Create: `frontend/src/lib/reconciliation.ts`
- Modify: `frontend/vite.config.ts`

**Interfaces:**
- Consumes: `authHeaders()` from `frontend/src/lib/auth.ts` (existing)
- Produces: `login(email, password): Promise<void>` (stores the token as a side effect); `listTenants(): Promise<Tenant[]>`; `runReconciliation`, `getConflicts`, `resolveConflict`, `getReport` — all typed against the backend schemas from Task 3 and Task 4

No backend to talk to for automated tests here (no frontend test infra, per Global Constraints) — this task is verified by the TypeScript compiler and by Task 9's manual browser check.

- [ ] **Step 1: Add `login()` to `frontend/src/lib/auth.ts`**

Add at the end of `frontend/src/lib/auth.ts` (the existing `getToken`/`setToken`/`authHeaders` stay as-is):

```typescript
export async function login(email: string, password: string): Promise<void> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: { message?: string } })?.detail?.message ?? `HTTP ${res.status}`)
  }
  const body = (await res.json()) as { access_token: string }
  setToken(body.access_token)
}
```

- [ ] **Step 2: Create `frontend/src/lib/tenants.ts`**

```typescript
import { authHeaders } from './auth'

export interface Tenant {
  id: string
  name: string
}

export async function listTenants(): Promise<Tenant[]> {
  const res = await fetch('/tenants', { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<Tenant[]>
}
```

- [ ] **Step 3: Create `frontend/src/lib/reconciliation.ts`**

```typescript
import { authHeaders } from './auth'

export interface RunRequestBody {
  tenant_id: string
  date_debut?: string | null
  date_fin?: string | null
}

export interface RunResponse {
  run_id: string
  tenant_id: string
  date_debut: string
  date_fin: string
}

export interface TransactionData {
  id: string
  montant: string
  date: string
  libelle: string
}

export interface FactureData {
  id: string
  montant: string
  date: string
  fournisseur: string
}

export interface Conflict {
  transaction: TransactionData
  facture: FactureData | null
  raison: string
  composite_score: number
}

export interface MatchData {
  facture_id: string
  transaction_id: string
  confidence: number
  ecart_montant: string
  statut: string
}

export interface Report {
  tenant_id: string
  date_debut: string
  date_fin: string
  total_transactions: number
  total_rapprochees: number
  total_non_rapprochees: number
  total_ecarts: number
  matches: MatchData[]
  unmatched: TransactionData[]
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: { message?: string } })?.detail?.message ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export async function runReconciliation(body: RunRequestBody): Promise<RunResponse> {
  const res = await fetch('/reconciliation/run', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return json<RunResponse>(res)
}

export async function getConflicts(runId: string): Promise<Conflict[]> {
  const res = await fetch(`/reconciliation/run/${runId}/conflicts`, { headers: authHeaders() })
  return json<Conflict[]>(res)
}

export async function resolveConflict(
  runId: string,
  conflictId: string,
  decision: 'confirmer' | 'rejeter' | 'ecart_accepte',
): Promise<void> {
  const res = await fetch(`/reconciliation/run/${runId}/resolve`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ conflict_id: conflictId, decision }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function getReport(runId: string): Promise<Report> {
  const res = await fetch(`/reconciliation/run/${runId}/report`, { headers: authHeaders() })
  return json<Report>(res)
}
```

- [ ] **Step 4: Add the missing proxy entries to `vite.config.ts`**

The dev proxy currently only forwards `/api` and `/admin` to the backend — `/auth`, `/reconciliation`, and `/tenants` are called directly by the new client code and need entries too, or Vite's own dev server 404s them. Replace the `proxy` block in `frontend/vite.config.ts`:

```typescript
    proxy: {
      '/api': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/reconciliation': 'http://localhost:8000',
      '/tenants': 'http://localhost:8000',
    },
```

- [ ] **Step 5: Type-check the frontend**

```bash
cd frontend && npx tsc -b --noEmit
```

Expected: no errors (these files aren't imported anywhere yet, but they must still compile standalone).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/auth.ts frontend/src/lib/tenants.ts frontend/src/lib/reconciliation.ts frontend/vite.config.ts
git commit -m "feat(frontend): add auth login, tenants, and reconciliation API clients"
```

---

## Task 6: Login page

**Files:**
- Create: `frontend/src/pages/Login.tsx`

**Interfaces:**
- Consumes: `login` from `frontend/src/lib/auth.ts` (Task 5)
- Produces: `Login` component (default export), routed in `App.tsx` by Task 9 once `Reconciliation.tsx` also exists — wiring both new routes together avoids an intermediate commit that references a page that doesn't exist yet.

- [ ] **Step 1: Create `frontend/src/pages/Login.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../lib/auth'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
      navigate('/reconciliation')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur de connexion')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: '80px auto', padding: 24 }}>
      <h1>Connexion</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>Email</label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required />
        </div>
        <div>
          <label>Mot de passe</label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        {error && <p style={{ color: 'red' }}>{error}</p>}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Connexion...' : 'Se connecter'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Login.tsx
git commit -m "feat(frontend): add login page"
```

---

## Task 7: `ConflictReview` component

**Files:**
- Create: `frontend/src/components/ConflictReview.tsx`

**Interfaces:**
- Consumes: `Conflict` type from `frontend/src/lib/reconciliation.ts` (Task 5)
- Produces: `ConflictReview` component (default export), props `{ conflict: Conflict, index: number, total: number, onDecide: (decision: 'confirmer' | 'rejeter' | 'ecart_accepte') => void, deciding: boolean }` — consumed by `Reconciliation.tsx` in Task 9.

- [ ] **Step 1: Create `frontend/src/components/ConflictReview.tsx`**

```tsx
import type { Conflict } from '../lib/reconciliation'

interface Props {
  conflict: Conflict
  index: number
  total: number
  onDecide: (decision: 'confirmer' | 'rejeter' | 'ecart_accepte') => void
  deciding: boolean
}

export default function ConflictReview({ conflict, index, total, onDecide, deciding }: Props) {
  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <p>Conflit {index} / {total}</p>
      <p>Raison : {conflict.raison} (score {conflict.composite_score.toFixed(2)})</p>
      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
          <h3>Transaction</h3>
          <p>Montant : {conflict.transaction.montant}</p>
          <p>Date : {conflict.transaction.date}</p>
          <p>Libellé : {conflict.transaction.libelle}</p>
        </div>
        <div style={{ flex: 1, border: '1px solid #ddd', padding: 16, borderRadius: 8 }}>
          <h3>Facture candidate</h3>
          {conflict.facture ? (
            <>
              <p>Montant : {conflict.facture.montant}</p>
              <p>Date : {conflict.facture.date}</p>
              <p>Fournisseur : {conflict.facture.fournisseur}</p>
            </>
          ) : (
            <p>Aucune facture candidate</p>
          )}
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        <button disabled={deciding} onClick={() => onDecide('confirmer')}>Confirmer</button>
        <button disabled={deciding} onClick={() => onDecide('ecart_accepte')} style={{ marginLeft: 8 }}>
          Écart accepté
        </button>
        <button disabled={deciding} onClick={() => onDecide('rejeter')} style={{ marginLeft: 8, color: 'red' }}>
          Rejeter
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ConflictReview.tsx
git commit -m "feat(frontend): add ConflictReview component"
```

---

## Task 8: `ReconciliationReport` component

**Files:**
- Create: `frontend/src/components/ReconciliationReport.tsx`

**Interfaces:**
- Consumes: `Report` type from `frontend/src/lib/reconciliation.ts` (Task 5)
- Produces: `ReconciliationReport` component (default export), props `{ report: Report, onRestart: () => void }` — consumed by `Reconciliation.tsx` in Task 9.

- [ ] **Step 1: Create `frontend/src/components/ReconciliationReport.tsx`**

```tsx
import type { Report } from '../lib/reconciliation'

interface Props {
  report: Report
  onRestart: () => void
}

export default function ReconciliationReport({ report, onRestart }: Props) {
  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <h1>Rapport de rapprochement</h1>
      <p>Transactions : {report.total_transactions}</p>
      <p>Rapprochées : {report.total_rapprochees}</p>
      <p>Non rapprochées : {report.total_non_rapprochees}</p>
      <p>Écarts : {report.total_ecarts}</p>

      <h3>Matches</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Facture</th>
            <th>Transaction</th>
            <th>Statut</th>
            <th>Écart</th>
          </tr>
        </thead>
        <tbody>
          {report.matches.map(m => (
            <tr key={`${m.facture_id}-${m.transaction_id}`}>
              <td>{m.facture_id}</td>
              <td>{m.transaction_id}</td>
              <td>{m.statut}</td>
              <td>{m.ecart_montant}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Non rapprochées</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Montant</th>
            <th>Date</th>
            <th>Libellé</th>
          </tr>
        </thead>
        <tbody>
          {report.unmatched.map(t => (
            <tr key={t.id}>
              <td>{t.id}</td>
              <td>{t.montant}</td>
              <td>{t.date}</td>
              <td>{t.libelle}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button onClick={onRestart} style={{ marginTop: 16 }}>Nouveau rapprochement</button>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/ReconciliationReport.tsx
git commit -m "feat(frontend): add ReconciliationReport component"
```

---

## Task 9: `Reconciliation` page + wire routing

**Files:**
- Create: `frontend/src/pages/Reconciliation.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `listTenants`/`Tenant` (Task 5), `runReconciliation`/`getConflicts`/`resolveConflict`/`getReport`/`Conflict`/`Report` (Task 5), `ConflictReview` (Task 7), `ReconciliationReport` (Task 8), `login`/`getToken` (existing + Task 5)
- Produces: `Reconciliation` component (default export), routed as the app's default landing page

The three-step flow lives as local state in one page — trigger fetches tenants and starts a run; once a run exists, conflicts are refetched after every decision until none remain, at which point the report is fetched. `totalConflicts` is captured once (at the first fetch after triggering the run) so the "Conflit X / N" counter can count *down* correctly as the refetched list shrinks — the API itself has no notion of "total", only "currently pending".

- [ ] **Step 1: Create `frontend/src/pages/Reconciliation.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { listTenants, type Tenant } from '../lib/tenants'
import {
  runReconciliation,
  getConflicts,
  resolveConflict,
  getReport,
  type Conflict,
  type Report,
} from '../lib/reconciliation'
import ConflictReview from '../components/ConflictReview'
import ReconciliationReport from '../components/ReconciliationReport'

type Step = 'trigger' | 'review' | 'report'

export default function Reconciliation() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenantId, setTenantId] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [step, setStep] = useState<Step>('trigger')
  const [runId, setRunId] = useState<string | null>(null)
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [totalConflicts, setTotalConflicts] = useState(0)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    listTenants()
      .then(setTenants)
      .catch(err => setError(err instanceof Error ? err.message : 'Erreur de chargement des tenants'))
  }, [])

  const advanceAfter = async (id: string, previousTotal: number) => {
    const pending = await getConflicts(id)
    if (pending.length === 0) {
      setReport(await getReport(id))
      setStep('report')
    } else {
      setConflicts(pending)
      setTotalConflicts(Math.max(previousTotal, pending.length))
      setStep('review')
    }
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const run = await runReconciliation({
        tenant_id: tenantId,
        date_debut: dateDebut || null,
        date_fin: dateFin || null,
      })
      setRunId(run.run_id)
      await advanceAfter(run.run_id, 0)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du lancement')
    } finally {
      setLoading(false)
    }
  }

  const handleDecide = async (decision: 'confirmer' | 'rejeter' | 'ecart_accepte') => {
    if (!runId || conflicts.length === 0) return
    setLoading(true)
    setError(null)
    try {
      await resolveConflict(runId, conflicts[0].transaction.id, decision)
      await advanceAfter(runId, totalConflicts)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la décision')
    } finally {
      setLoading(false)
    }
  }

  const handleRestart = () => {
    setStep('trigger')
    setRunId(null)
    setConflicts([])
    setTotalConflicts(0)
    setReport(null)
  }

  if (step === 'review' && conflicts.length > 0) {
    return (
      <ConflictReview
        conflict={conflicts[0]}
        index={totalConflicts - conflicts.length + 1}
        total={totalConflicts}
        onDecide={handleDecide}
        deciding={loading}
      />
    )
  }

  if (step === 'report' && report) {
    return <ReconciliationReport report={report} onRestart={handleRestart} />
  }

  return (
    <div style={{ maxWidth: 500, margin: '40px auto', padding: 24 }}>
      <h1>Lancer un rapprochement</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <div>
        <label>Tenant</label>
        <select value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">-- choisir --</option>
          {tenants.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label>Date début (optionnel)</label>
        <input type="date" value={dateDebut} onChange={e => setDateDebut(e.target.value)} />
      </div>
      <div>
        <label>Date fin (optionnel)</label>
        <input type="date" value={dateFin} onChange={e => setDateFin(e.target.value)} />
      </div>
      <button onClick={() => void handleRun()} disabled={!tenantId || loading}>
        {loading ? 'Lancement...' : 'Lancer le rapprochement'}
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Wire routing in `frontend/src/App.tsx`**

Replace the full contents of `frontend/src/App.tsx`:

```tsx
import { type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AdminIntegrations from './pages/AdminIntegrations'
import Login from './pages/Login'
import Reconciliation from './pages/Reconciliation'
import { getToken } from './lib/auth'

function RequireAuth({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/reconciliation"
          element={
            <RequireAuth>
              <Reconciliation />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/integrations"
          element={
            <RequireAuth>
              <AdminIntegrations />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/reconciliation" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
```

- [ ] **Step 3: Type-check the frontend**

```bash
cd frontend && npx tsc -b --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Reconciliation.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add Reconciliation page and wire routing"
```

---

## Task 10: Manual verification in browser

**Files:** none — verification only.

- [ ] **Step 1: Start the backend**

```bash
DATABASE_URL=postgresql+asyncpg://comptis_app:app_secret@localhost:5432/comptis_dev \
JWT_SECRET_KEY=dev-secret-key-32-characters-min \
COMPTIS_ENCRYPTION_KEY=ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg= \
arch -arm64 uv run uvicorn comptis.interface.api.main:app --reload
```

(adjust `DATABASE_URL` to a running local Postgres with migrations applied — `docker compose up -d postgres && arch -arm64 uv run alembic upgrade head`)

- [ ] **Step 2: Start the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Seed a user with a tenant**

Register via `POST /auth/login` isn't enough on its own — a fresh user has no memberships, so `/tenants` will be empty and the trigger screen has nothing to select. Register a user through the UI or `curl -X POST http://localhost:8000/auth/register -d '{"email":"...", "password":"..."}' -H 'Content-Type: application/json'`, then insert an `organizations` + `tenants` + `memberships(role='accountant')` row for that user directly in Postgres (same shape as the `admin_identity` test fixture in Task 1).

- [ ] **Step 4: Walk the flow in the browser**

- Open `http://localhost:5173` → redirected to `/login`.
- Log in → redirected to `/reconciliation`.
- Confirm the seeded tenant appears in the dropdown.
- Launch a run. (If no real PNiCompta MCP/API backend is configured, this will error at the graph's fetch step — that's expected outside a fully wired environment; confirm the error surfaces in the UI rather than a blank screen, and stop here if there's no MCP backend available to test the review/report steps live.)
- If a run does produce conflicts: confirm each conflict shows transaction and facture side by side, the three decision buttons work, the counter decrements correctly, and reaching zero pending conflicts shows the report.
- Confirm "Nouveau rapprochement" returns to the trigger screen with a clean state.

- [ ] **Step 5: Report the outcome**

No commit for this task — it's a checklist, not a code change. Note in the final summary which parts of Step 4 were actually exercised (login/trigger/routing are always verifiable; review/report depend on a working MCP backend being available).

---

## Self-Review

**Spec coverage:**
- ✅ Migrate `require_api_key` → `require_user` on `POST /run`, `POST /resolve` → Task 4
- ✅ Add `require_user` to `GET .../conflicts`, `GET .../report` (previously unauthenticated) → Task 4
- ✅ `org_id` derived from `tenant_id` instead of the auth dependency → Task 4
- ✅ Tenant-ownership check on run-reading endpoints → Task 4
- ✅ `ConflictSchema.facture` → Task 4
- ✅ `TenantRepository.list_visible` → Task 2
- ✅ `GET /tenants` → Task 3
- ✅ Login page → Task 6
- ✅ Route guard → Task 9
- ✅ Trigger step (tenant + dates) → Task 9
- ✅ Review step (wizard, three decisions, counter) → Tasks 7, 9
- ✅ Report step → Tasks 8, 9
- ✅ Backend TDD tests (domain/application-level RLS test, interface integration tests) → Tasks 2, 3, 4
- ✅ Frontend manual verification only, no test infra added → Task 10
- ✅ Out of scope confirmed unaddressed: run history/persistence, manual matching of unmatched transactions, role-differentiated access — none of these appear in any task

**Type consistency:**
- `TenantRepository.list_visible(session) -> list[Tenant]` — declared in the Task 2 port, implemented in Task 2, consumed in Task 3's router ✅
- `FactureSchema` fields (`id: str`, `montant: Decimal`, `date: date`, `fournisseur: str`) match `Facture` domain entity fields used to construct it in Task 4 ✅
- `ConflictSchema.facture: FactureSchema | None` — matches `Conflict.facture: Facture | None` from `domain/rapprochement/entities.py` ✅
- Frontend `Conflict`/`Report`/`Tenant`/`RunResponse` types (Task 5) match the Pydantic schemas serialized by Tasks 3-4: `Decimal` fields typed as `string` (confirmed Pydantic v2 serializes `Decimal` as JSON string), `float` fields (`composite_score`, `confidence`) typed as `number` ✅
- `ConflictReview` props (Task 7) and `ReconciliationReport` props (Task 8) match exactly how `Reconciliation.tsx` calls them in Task 9 ✅
- `admin_identity`/`admin_token`/`admin_tenant_id` fixtures (Task 1) match every later test's fixture parameter names (`admin_token: str`, `admin_tenant_id: str`) ✅


