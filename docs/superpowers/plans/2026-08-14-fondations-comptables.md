# Fondations Comptables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Comptis its own persisted accounting data — a per-tenant chart of accounts (`comptes_pcg`, imported from PNiCompta's existing categories) and an `ecriture` (accounting entry) created automatically every time a fournisseur reconciliation match is confirmed — as the foundation later bricks (categorization engine, review UI) build on.

**Architecture:** New `domain/comptabilite/` + `application/comptabilite/` modules, following the exact Clean Architecture layering already used by `rapprochement`. Two new tables (`comptes_pcg`, `ecritures`), RLS keyed on `app.current_tenant_id` (the GUC `run_reconciliation` already sets correctly). Two integration points wire into the *existing* match-confirmation code paths — the auto-match branches in the LangGraph `match` node, and the human-confirm branch in `resolve_conflict` — both of which must now also explicitly set `app.current_tenant_id` before touching the new tables (the auto-match path already has it from `run_reconciliation`; `resolve_conflict` does not, and must gain it in this plan). `_build_mcp_client_for_org` is extracted from `rapprochement/router.py` into a shared `infrastructure/mcp/client_factory.py` since the new admin endpoint needs it too.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, Alembic, FastAPI, pytest + testcontainers (existing stack, no new dependencies).

## Global Constraints

- Clean Architecture: domain ← application ← infrastructure ← interface. No layer imports from an outer layer.
- RLS on every new table, keyed on `app.current_tenant_id` via the existing `set_tenant_context()` helper — never a subquery through `tenants` (that pattern is exactly what caused the GUC-name bug fixed in migration 0005; a direct `tenant_id = current_setting(...)::uuid` comparison is simpler and was not the buggy part).
- `pytestmark = pytest.mark.asyncio(loop_scope="session")` on every test module using session-scoped fixtures.
- Integration tests marked `@pytest.mark.integration`, run via `arch -arm64 uv run pytest -v -m integration` on this machine (Rosetta shell/arm64 venv mismatch — prefix every `uv run` with `arch -arm64`).
- Commit message format: `type(scope): description`.
- Money fields are `Decimal`, never `float`.
- `Ecriture.transaction_id`/`facture_id` are PNiCompta's own string IDs (opaque, not FKs into any Comptis table) — same convention as `domain/rapprochement/entities.py`.

---

## File Map

**New files:**
```
src/comptis/domain/comptabilite/__init__.py
src/comptis/domain/comptabilite/value_objects.py
src/comptis/domain/comptabilite/entities.py

src/comptis/application/comptabilite/__init__.py
src/comptis/application/comptabilite/ports.py
src/comptis/application/comptabilite/use_cases.py

src/comptis/infrastructure/db/migrations/versions/0006_add_comptabilite_tables.py
src/comptis/infrastructure/db/comptabilite_repository.py
src/comptis/infrastructure/mcp/client_factory.py

src/comptis/interface/api/admin/comptabilite/__init__.py
src/comptis/interface/api/admin/comptabilite/schemas.py
src/comptis/interface/api/admin/comptabilite/router.py

tests/domain/comptabilite/__init__.py
tests/domain/comptabilite/test_entities.py

tests/application/comptabilite/__init__.py
tests/application/comptabilite/conftest.py
tests/application/comptabilite/test_use_cases.py

tests/infrastructure/db/comptabilite/__init__.py
tests/infrastructure/db/comptabilite/conftest.py
tests/infrastructure/db/comptabilite/test_repositories.py
tests/infrastructure/db/comptabilite/test_isolation.py

tests/interface/api/test_admin_comptabilite.py
```

**Modified files:**
```
src/comptis/infrastructure/db/models.py                        → add CompteComptableModel, EcritureModel
src/comptis/infrastructure/mcp/pnicompta_client.py              → add list_comptes()
src/comptis/interface/api/rapprochement/router.py               → use shared client_factory; resolve_conflict sets tenant context + creates écriture
src/comptis/infrastructure/agents/rapprochement/nodes/match.py  → creates écriture at the 3 mark_rapprochement sites
src/comptis/infrastructure/agents/rapprochement/graph.py        → build_reconciliation_graph/make_match_node take ecriture_repo
src/comptis/interface/api/main.py                                → register admin/comptabilite router
tests/interface/api/conftest.py                                  → (read-only reference; no change needed — admin_tenant_id already exposed)
```

---

## Task 1: Domain — entities and value objects

**Files:**
- Create: `src/comptis/domain/comptabilite/__init__.py`
- Create: `src/comptis/domain/comptabilite/value_objects.py`
- Create: `src/comptis/domain/comptabilite/entities.py`
- Test: `tests/domain/comptabilite/__init__.py`
- Test: `tests/domain/comptabilite/test_entities.py`

**Interfaces:**
- Produces: `StatutEcriture` (StrEnum: `A_CATEGORISER`, `CATEGORISEE`, `VALIDEE`), `CompteComptable` (tenant_id, numero, libelle, classe, id, created_at), `Ecriture` (tenant_id, transaction_id, facture_id, montant, date, compte_id, statut, id, created_at)

- [ ] **Step 1: Create `__init__.py` files**

```bash
mkdir -p src/comptis/domain/comptabilite tests/domain/comptabilite
touch src/comptis/domain/comptabilite/__init__.py
touch tests/domain/comptabilite/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/domain/comptabilite/test_entities.py`:

```python
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture
from comptis.domain.comptabilite.value_objects import StatutEcriture


def test_compte_comptable_auto_generates_uuid():
    compte = CompteComptable(tenant_id=uuid4(), numero="625100", libelle="Voyages", classe=6)
    assert isinstance(compte.id, UUID)


def test_compte_comptable_has_created_at():
    compte = CompteComptable(tenant_id=uuid4(), numero="625100", libelle="Voyages", classe=6)
    assert isinstance(compte.created_at, datetime)


def test_ecriture_defaults_to_a_categoriser_with_no_compte():
    ecriture = Ecriture(
        tenant_id=uuid4(),
        transaction_id="t1",
        facture_id="f1",
        montant=Decimal("7.10"),
        date=date(2026, 7, 31),
    )
    assert ecriture.compte_id is None
    assert ecriture.statut == StatutEcriture.A_CATEGORISER


def test_ecriture_can_be_created_with_explicit_compte():
    compte_id = uuid4()
    ecriture = Ecriture(
        tenant_id=uuid4(),
        transaction_id="t1",
        facture_id="f1",
        montant=Decimal("7.10"),
        date=date(2026, 7, 31),
        compte_id=compte_id,
        statut=StatutEcriture.CATEGORISEE,
    )
    assert ecriture.compte_id == compte_id
    assert ecriture.statut == StatutEcriture.CATEGORISEE


def test_two_ecritures_have_different_ids():
    a = Ecriture(tenant_id=uuid4(), transaction_id="t1", facture_id="f1", montant=Decimal("1"), date=date(2026, 1, 1))
    b = Ecriture(tenant_id=uuid4(), transaction_id="t2", facture_id="f2", montant=Decimal("1"), date=date(2026, 1, 1))
    assert a.id != b.id


def test_statut_ecriture_is_string():
    assert isinstance(StatutEcriture.A_CATEGORISER, str)
    assert StatutEcriture.A_CATEGORISER == "a_categoriser"
    assert StatutEcriture.CATEGORISEE == "categorisee"
    assert StatutEcriture.VALIDEE == "validee"
```

- [ ] **Step 3: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/domain/comptabilite/test_entities.py -v
```

Expected: `ModuleNotFoundError: No module named 'comptis.domain.comptabilite.entities'`

- [ ] **Step 4: Implement `value_objects.py`**

Create `src/comptis/domain/comptabilite/value_objects.py`:

```python
from enum import StrEnum


class StatutEcriture(StrEnum):
    A_CATEGORISER = "a_categoriser"  # compte_id est NULL — seul statut atteint par cette brique
    CATEGORISEE = "categorisee"      # compte proposé par le moteur (brique SP4)
    VALIDEE = "validee"              # confirmée par un humain (brique SP5)
```

- [ ] **Step 5: Implement `entities.py`**

Create `src/comptis/domain/comptabilite/entities.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from .value_objects import StatutEcriture


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class CompteComptable:
    tenant_id: UUID
    numero: str
    libelle: str
    classe: int
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Ecriture:
    tenant_id: UUID
    transaction_id: str
    facture_id: str
    montant: Decimal
    date: date_
    compte_id: UUID | None = None
    statut: StatutEcriture = StatutEcriture.A_CATEGORISER
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
```

- [ ] **Step 6: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/domain/comptabilite/test_entities.py -v
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add src/comptis/domain/comptabilite/ tests/domain/comptabilite/
git commit -m "feat(domain): add CompteComptable and Ecriture entities"
```

---

## Task 2: Application — ports and use cases

**Files:**
- Create: `src/comptis/application/comptabilite/__init__.py`
- Create: `src/comptis/application/comptabilite/ports.py`
- Create: `src/comptis/application/comptabilite/use_cases.py`
- Test: `tests/application/comptabilite/__init__.py`
- Test: `tests/application/comptabilite/conftest.py`
- Test: `tests/application/comptabilite/test_use_cases.py`

**Interfaces:**
- Consumes: `CompteComptable`, `Ecriture`, `StatutEcriture` from Task 1
- Produces:
  - `CompteComptableRepository` Protocol: `save(compte) -> None`, `list_by_tenant(tenant_id) -> list[CompteComptable]`
  - `EcritureRepository` Protocol: `save(ecriture) -> None`
  - `PlanComptableSource` Protocol: `list_comptes() -> list[tuple[str, str]]` (numero, libelle)
  - `ImporterPlanComptable(compte_repo, source).execute(tenant_id: UUID) -> list[CompteComptable]`
  - `CreerEcritureDepuisMatch(ecriture_repo).execute(tenant_id: UUID, transaction_id: str, facture_id: str, montant: Decimal, date_: date) -> Ecriture`

- [ ] **Step 1: Create `__init__.py` files**

```bash
mkdir -p src/comptis/application/comptabilite tests/application/comptabilite
touch src/comptis/application/comptabilite/__init__.py
touch tests/application/comptabilite/__init__.py
```

- [ ] **Step 2: Write ports**

Create `src/comptis/application/comptabilite/ports.py`:

```python
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture


class CompteComptableRepository(Protocol):
    async def save(self, compte: CompteComptable) -> None: ...
    async def list_by_tenant(self, tenant_id: UUID) -> list[CompteComptable]: ...


class EcritureRepository(Protocol):
    async def save(self, ecriture: Ecriture) -> None: ...


class PlanComptableSource(Protocol):
    """Source externe d'un plan de comptes à importer (ex: PNiCompta)."""

    async def list_comptes(self) -> list[tuple[str, str]]:  # (numero, libelle)
        ...
```

- [ ] **Step 3: Create in-memory fakes in `conftest.py`**

Create `tests/application/comptabilite/conftest.py`:

```python
import pytest
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture


class FakeCompteComptableRepository:
    def __init__(self) -> None:
        self.saved: list[CompteComptable] = []

    async def save(self, compte: CompteComptable) -> None:
        self.saved.append(compte)

    async def list_by_tenant(self, tenant_id: UUID) -> list[CompteComptable]:
        return [c for c in self.saved if c.tenant_id == tenant_id]


class FakeEcritureRepository:
    def __init__(self) -> None:
        self.saved: list[Ecriture] = []

    async def save(self, ecriture: Ecriture) -> None:
        self.saved.append(ecriture)


class FakePlanComptableSource:
    def __init__(self, comptes: list[tuple[str, str]]) -> None:
        self._comptes = comptes

    async def list_comptes(self) -> list[tuple[str, str]]:
        return self._comptes


@pytest.fixture
def compte_repo() -> FakeCompteComptableRepository:
    return FakeCompteComptableRepository()


@pytest.fixture
def ecriture_repo() -> FakeEcritureRepository:
    return FakeEcritureRepository()
```

- [ ] **Step 4: Write the failing use case tests**

Create `tests/application/comptabilite/test_use_cases.py`:

```python
from datetime import date
from decimal import Decimal
from uuid import uuid4

from comptis.application.comptabilite.use_cases import (
    CreerEcritureDepuisMatch,
    ImporterPlanComptable,
)
from comptis.domain.comptabilite.value_objects import StatutEcriture

from .conftest import FakePlanComptableSource


async def test_importer_plan_comptable_saves_each_compte(compte_repo):
    tenant_id = uuid4()
    source = FakePlanComptableSource([("625100", "Voyages et déplacements"), ("606400", "Fournitures")])
    use_case = ImporterPlanComptable(compte_repo=compte_repo, source=source)

    comptes = await use_case.execute(tenant_id)

    assert len(comptes) == 2
    assert len(compte_repo.saved) == 2
    numeros = {c.numero for c in compte_repo.saved}
    assert numeros == {"625100", "606400"}


async def test_importer_plan_comptable_derives_classe_from_numero():
    tenant_id = uuid4()
    from tests.application.comptabilite.conftest import FakeCompteComptableRepository

    repo = FakeCompteComptableRepository()
    source = FakePlanComptableSource([("625100", "Voyages")])
    use_case = ImporterPlanComptable(compte_repo=repo, source=source)

    comptes = await use_case.execute(tenant_id)

    assert comptes[0].classe == 6


async def test_importer_plan_comptable_sets_tenant_id_on_every_compte(compte_repo):
    tenant_id = uuid4()
    source = FakePlanComptableSource([("625100", "Voyages"), ("606400", "Fournitures")])
    use_case = ImporterPlanComptable(compte_repo=compte_repo, source=source)

    comptes = await use_case.execute(tenant_id)

    assert all(c.tenant_id == tenant_id for c in comptes)


async def test_creer_ecriture_depuis_match_saves_and_returns(ecriture_repo):
    tenant_id = uuid4()
    use_case = CreerEcritureDepuisMatch(ecriture_repo=ecriture_repo)

    ecriture = await use_case.execute(
        tenant_id=tenant_id,
        transaction_id="t1",
        facture_id="f1",
        montant=Decimal("7.10"),
        date_=date(2026, 7, 31),
    )

    assert ecriture.tenant_id == tenant_id
    assert ecriture.transaction_id == "t1"
    assert ecriture.facture_id == "f1"
    assert ecriture.montant == Decimal("7.10")
    assert ecriture.compte_id is None
    assert ecriture.statut == StatutEcriture.A_CATEGORISER
    assert ecriture_repo.saved == [ecriture]
```

- [ ] **Step 5: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/application/comptabilite/test_use_cases.py -v
```

Expected: `ModuleNotFoundError: No module named 'comptis.application.comptabilite.use_cases'`

- [ ] **Step 6: Implement `use_cases.py`**

Create `src/comptis/application/comptabilite/use_cases.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture

from .ports import CompteComptableRepository, EcritureRepository, PlanComptableSource


@dataclass
class ImporterPlanComptable:
    compte_repo: CompteComptableRepository
    source: PlanComptableSource

    async def execute(self, tenant_id: UUID) -> list[CompteComptable]:
        comptes = []
        for numero, libelle in await self.source.list_comptes():
            classe = int(numero[0]) if numero[:1].isdigit() else 0
            compte = CompteComptable(
                tenant_id=tenant_id, numero=numero, libelle=libelle, classe=classe,
            )
            await self.compte_repo.save(compte)
            comptes.append(compte)
        return comptes


@dataclass
class CreerEcritureDepuisMatch:
    ecriture_repo: EcritureRepository

    async def execute(
        self,
        tenant_id: UUID,
        transaction_id: str,
        facture_id: str,
        montant: Decimal,
        date_: date,
    ) -> Ecriture:
        ecriture = Ecriture(
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            facture_id=facture_id,
            montant=montant,
            date=date_,
        )
        await self.ecriture_repo.save(ecriture)
        return ecriture
```

- [ ] **Step 7: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/application/comptabilite/test_use_cases.py -v
```

Expected: `4 passed`

- [ ] **Step 8: Commit**

```bash
git add src/comptis/application/comptabilite/ tests/application/comptabilite/
git commit -m "feat(application): add ImporterPlanComptable and CreerEcritureDepuisMatch use cases"
```

---

## Task 3: Infrastructure — migration and ORM models

**Files:**
- Create: `src/comptis/infrastructure/db/migrations/versions/0006_add_comptabilite_tables.py`
- Modify: `src/comptis/infrastructure/db/models.py`

**Interfaces:**
- Produces: `comptes_pcg` table (`id`, `tenant_id`, `numero`, `libelle`, `classe`, `created_at`, unique on `(tenant_id, numero)`), `ecritures` table (`id`, `tenant_id`, `transaction_id`, `facture_id`, `montant`, `date`, `compte_id` nullable, `statut`, `created_at`, unique on `(tenant_id, transaction_id)`). Both RLS-scoped on `app.current_tenant_id`. `CompteComptableModel`, `EcritureModel` ORM classes.

No dedicated unit tests here — verified by Task 4's repository/RLS integration tests.

- [ ] **Step 1: Create the migration**

Create `src/comptis/infrastructure/db/migrations/versions/0006_add_comptabilite_tables.py`:

```python
"""Add comptes_pcg and ecritures tables

Comptis's own accounting data — a per-tenant chart of accounts and the
accounting entries created when a fournisseur reconciliation match is
confirmed. RLS is keyed directly on app.current_tenant_id (no subquery
through tenants) — a direct comparison, the pattern proven correct by the
0005 fix, not the subquery pattern that caused that bug.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "comptes_pcg",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.String(20), nullable=False),
        sa.Column("libelle", sa.String(255), nullable=False),
        sa.Column("classe", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "numero", name="uq_comptes_pcg_tenant_numero"),
    )
    op.create_table(
        "ecritures",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("tenant_id", sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transaction_id", sa.String(64), nullable=False),
        sa.Column("facture_id", sa.String(64), nullable=False),
        sa.Column("montant", sa.Numeric(12, 2), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("compte_id", sa.Uuid, sa.ForeignKey("comptes_pcg.id", ondelete="SET NULL"), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="a_categoriser"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_ecritures_tenant_transaction"),
    )

    for table in ("comptes_pcg", "ecritures"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """)
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO comptis_app")


def downgrade() -> None:
    for table in ("comptes_pcg", "ecritures"):
        op.execute(f"REVOKE ALL PRIVILEGES ON {table} FROM comptis_app")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("ecritures")
    op.drop_table("comptes_pcg")
```

- [ ] **Step 2: Add the ORM models**

In `src/comptis/infrastructure/db/models.py`, add `date` to the existing `datetime` import at the top:

```python
from datetime import date as dt_date, datetime, timezone
```

Then append at the end of the file:

```python
class CompteComptableModel(Base):
    __tablename__ = "comptes_pcg"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    numero: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    libelle: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    classe: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "numero", name="uq_comptes_pcg_tenant_numero"),
    )


class EcritureModel(Base):
    __tablename__ = "ecritures"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    facture_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    montant: Mapped[Decimal] = mapped_column(sa.Numeric(12, 2), nullable=False)
    date: Mapped[dt_date] = mapped_column(sa.Date, nullable=False)
    compte_id: Mapped[UUID | None] = mapped_column(
        sa.Uuid, sa.ForeignKey("comptes_pcg.id", ondelete="SET NULL"), nullable=True
    )
    statut: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="a_categoriser")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "transaction_id", name="uq_ecritures_tenant_transaction"),
    )
```

- [ ] **Step 3: Run the migration against a local Postgres to confirm it applies cleanly**

```bash
docker compose up -d postgres
arch -arm64 uv run alembic upgrade head
```

Expected output ends with: `Running upgrade 0005 -> 0006, Add comptes_pcg and ecritures tables`

- [ ] **Step 4: Commit**

```bash
git add src/comptis/infrastructure/db/migrations/versions/0006_add_comptabilite_tables.py src/comptis/infrastructure/db/models.py
git commit -m "feat(infra): add comptes_pcg and ecritures tables with RLS"
```

---

## Task 4: Infrastructure — repositories and RLS isolation tests

**Files:**
- Create: `src/comptis/infrastructure/db/comptabilite_repository.py`
- Test: `tests/infrastructure/db/comptabilite/__init__.py`
- Test: `tests/infrastructure/db/comptabilite/conftest.py`
- Test: `tests/infrastructure/db/comptabilite/test_repositories.py`
- Test: `tests/infrastructure/db/comptabilite/test_isolation.py`

**Interfaces:**
- Consumes: `CompteComptableModel`, `EcritureModel` from Task 3; `CompteComptable`, `Ecriture`, `StatutEcriture` from Task 1
- Produces: `SQLAlchemyCompteComptableRepository`, `SQLAlchemyEcritureRepository` — implement the Task 2 ports

- [ ] **Step 1: Create `__init__.py` and `conftest.py`**

```bash
mkdir -p tests/infrastructure/db/comptabilite
touch tests/infrastructure/db/comptabilite/__init__.py
```

Create `tests/infrastructure/db/comptabilite/conftest.py` (same shape as `tests/infrastructure/db/rapprochement/conftest.py` — its own container, not shared across test directories, matching this repo's existing convention):

```python
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16", username="postgres", password="test", dbname="comptis_test") as pg:
        yield pg


@pytest.fixture(scope="session")
def admin_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+psycopg://postgres:test@{host}:{port}/comptis_test"


@pytest.fixture(scope="session")
def app_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://comptis_app:app_secret@{host}:{port}/comptis_test"


@pytest.fixture(scope="session", autouse=True)
def run_migrations(admin_db_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", admin_db_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_engine(admin_db_url):
    engine = create_async_engine(
        admin_db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://"), echo=False
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_engine(app_db_url):
    engine = create_async_engine(app_db_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(app_engine):
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_tenant(admin_engine):
    """Create an org + tenant using the admin (superuser) engine and return the tenant_id."""
    from uuid import uuid4
    from sqlalchemy import text

    org_id = uuid4()
    tenant_id = uuid4()
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text(
                    "INSERT INTO organizations (id, name, type, created_at) "
                    "VALUES (:id, :name, :type, now())"
                ),
                {"id": str(org_id), "name": "Test Org", "type": "cabinet"},
            )
            await session.execute(
                text(
                    "INSERT INTO tenants (id, organization_id, name, created_at) "
                    "VALUES (:id, :org_id, :name, now())"
                ),
                {"id": str(tenant_id), "org_id": str(org_id), "name": "Test Tenant"},
            )
    return tenant_id, org_id
```

- [ ] **Step 2: Write the failing repository tests**

Create `tests/infrastructure/db/comptabilite/test_repositories.py`:

```python
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture
from comptis.infrastructure.db.comptabilite_repository import (
    SQLAlchemyCompteComptableRepository,
    SQLAlchemyEcritureRepository,
)
from comptis.infrastructure.db.tenant_context import set_tenant_context

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_save_and_list_compte_comptable(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyCompteComptableRepository(db_session)

    compte = CompteComptable(tenant_id=tenant_id, numero="625100", libelle="Voyages", classe=6)
    await repo.save(compte)

    comptes = await repo.list_by_tenant(tenant_id)
    assert len(comptes) == 1
    assert comptes[0].numero == "625100"
    assert comptes[0].libelle == "Voyages"


@pytest.mark.integration
async def test_save_compte_comptable_is_idempotent_on_conflict(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyCompteComptableRepository(db_session)

    await repo.save(CompteComptable(tenant_id=tenant_id, numero="606400", libelle="Fournitures", classe=6))
    await repo.save(CompteComptable(tenant_id=tenant_id, numero="606400", libelle="Fournitures (rejoué)", classe=6))

    comptes = await repo.list_by_tenant(tenant_id)
    matching = [c for c in comptes if c.numero == "606400"]
    assert len(matching) == 1


@pytest.mark.integration
async def test_save_and_retrieve_ecriture(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyEcritureRepository(db_session)

    ecriture = Ecriture(
        tenant_id=tenant_id, transaction_id="t1", facture_id="f1",
        montant=Decimal("7.10"), date=date(2026, 7, 31),
    )
    await repo.save(ecriture)

    from sqlalchemy import select
    from comptis.infrastructure.db.models import EcritureModel
    result = await db_session.execute(select(EcritureModel).where(EcritureModel.tenant_id == tenant_id))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].transaction_id == "t1"
    assert rows[0].compte_id is None
    assert rows[0].statut == "a_categoriser"


@pytest.mark.integration
async def test_save_ecriture_is_idempotent_on_same_transaction(db_session, seeded_tenant):
    tenant_id, org_id = seeded_tenant
    await set_tenant_context(db_session, tenant_id=tenant_id, organization_id=org_id)
    repo = SQLAlchemyEcritureRepository(db_session)

    await repo.save(Ecriture(tenant_id=tenant_id, transaction_id="t2", facture_id="f2", montant=Decimal("5"), date=date(2026, 1, 1)))
    await repo.save(Ecriture(tenant_id=tenant_id, transaction_id="t2", facture_id="f2", montant=Decimal("5"), date=date(2026, 1, 1)))

    from sqlalchemy import select
    from comptis.infrastructure.db.models import EcritureModel
    result = await db_session.execute(select(EcritureModel).where(EcritureModel.transaction_id == "t2"))
    assert len(result.scalars().all()) == 1
```

- [ ] **Step 3: Write the failing RLS isolation test**

Create `tests/infrastructure/db/comptabilite/test_isolation.py`:

```python
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.models import CompteComptableModel
from comptis.infrastructure.db.tenant_context import set_tenant_context

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_tenant_b_cannot_see_tenant_a_comptes(admin_engine, app_engine):
    from uuid import uuid4
    from sqlalchemy import text

    org_id = uuid4()
    tenant_a = uuid4()
    tenant_b = uuid4()
    compte_a = uuid4()

    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO organizations (id, name, type, created_at) VALUES (:id, 'Org', 'cabinet', now())"),
                {"id": str(org_id)},
            )
            for tid, name in [(tenant_a, "Tenant A"), (tenant_b, "Tenant B")]:
                await session.execute(
                    text("INSERT INTO tenants (id, organization_id, name, created_at) VALUES (:id, :org_id, :name, now())"),
                    {"id": str(tid), "org_id": str(org_id), "name": name},
                )
            await session.execute(
                text(
                    "INSERT INTO comptes_pcg (id, tenant_id, numero, libelle, classe, created_at) "
                    "VALUES (:id, :tenant_id, '625100', 'Voyages', 6, now())"
                ),
                {"id": str(compte_a), "tenant_id": str(tenant_a)},
            )

    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            await set_tenant_context(session, tenant_id=tenant_b)
            result = await session.execute(select(CompteComptableModel))
            visible = result.scalars().all()
            assert len(visible) == 0, f"RLS leak: tenant B can see {len(visible)} compte(s) belonging to tenant A"


@pytest.mark.integration
async def test_no_tenant_context_returns_empty(app_engine):
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            result = await session.execute(select(CompteComptableModel))
            assert result.scalars().all() == []
```

- [ ] **Step 4: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/infrastructure/db/comptabilite/ -v -m integration
```

Expected: `ModuleNotFoundError: No module named 'comptis.infrastructure.db.comptabilite_repository'`

- [ ] **Step 5: Implement the repositories**

Create `src/comptis/infrastructure/db/comptabilite_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.comptabilite.entities import CompteComptable, Ecriture
from comptis.domain.comptabilite.value_objects import StatutEcriture

from .models import CompteComptableModel, EcritureModel


def _compte_to_domain(m: CompteComptableModel) -> CompteComptable:
    return CompteComptable(
        id=m.id, tenant_id=m.tenant_id, numero=m.numero, libelle=m.libelle,
        classe=m.classe, created_at=m.created_at,
    )


class SQLAlchemyCompteComptableRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, compte: CompteComptable) -> None:
        stmt = (
            insert(CompteComptableModel)
            .values(
                id=compte.id, tenant_id=compte.tenant_id, numero=compte.numero,
                libelle=compte.libelle, classe=compte.classe, created_at=compte.created_at,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "numero"])
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_by_tenant(self, tenant_id: UUID) -> list[CompteComptable]:
        result = await self._session.execute(
            select(CompteComptableModel).where(CompteComptableModel.tenant_id == tenant_id)
        )
        return [_compte_to_domain(m) for m in result.scalars().all()]


class SQLAlchemyEcritureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, ecriture: Ecriture) -> None:
        stmt = (
            insert(EcritureModel)
            .values(
                id=ecriture.id, tenant_id=ecriture.tenant_id,
                transaction_id=ecriture.transaction_id, facture_id=ecriture.facture_id,
                montant=ecriture.montant, date=ecriture.date,
                compte_id=ecriture.compte_id, statut=ecriture.statut.value,
                created_at=ecriture.created_at,
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "transaction_id"])
        )
        await self._session.execute(stmt)
        await self._session.flush()
```

- [ ] **Step 6: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/infrastructure/db/comptabilite/ -v -m integration
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add src/comptis/infrastructure/db/comptabilite_repository.py tests/infrastructure/db/comptabilite/
git commit -m "feat(infra): add SQLAlchemy repositories for comptes_pcg and ecritures"
```

---

## Task 5: `PniComptaClient.list_comptes()`

**Files:**
- Modify: `src/comptis/infrastructure/mcp/pnicompta_client.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `PniComptaClient.list_comptes() -> list[tuple[str, str]]` — satisfies the `PlanComptableSource` Protocol from Task 2 (the method name must be exactly `list_comptes`, not e.g. `list_categories`, for structural typing to match)

`pnicompta_client.py` has no unit tests today (`list_transactions`/`list_factures`/`mark_rapprochement` were all verified manually against the real Planet Network International PNiCompta instance, not via a mocked-httpx unit suite) — this task follows that same established precedent rather than introducing a new testing pattern for one method. It's exercised for real by Task 7's admin endpoint, manually, the same way the rest of this file always has been.

- [ ] **Step 1: Add `list_comptes()`**

In `src/comptis/infrastructure/mcp/pnicompta_client.py`, add a new section after the `# Reconciliation` section and before `# Internal helpers`:

```python
    # ------------------------------------------------------------------
    # Plan comptable
    # ------------------------------------------------------------------

    async def list_comptes(self) -> list[tuple[str, str]]:
        """Implémente PlanComptableSource — lit les Category déjà configurées
        côté PNiCompta (account_number/account_label réels, posés par
        l'expert-comptable du client) plutôt que de deviner un plan de
        comptes générique.
        """
        data = await self._get("/categories/", {"page_size": 500})
        rows = data.get("results", data) if isinstance(data, dict) else data
        return [
            (r["account_number"], r.get("account_label") or r.get("name", ""))
            for r in rows
            if r.get("account_number")
        ]
```

- [ ] **Step 2: Manually verify against the real PNiCompta instance**

```bash
arch -arm64 uv run python -c "
import asyncio, os
from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient

async def main():
    client = PniComptaClient(base_url=os.environ['PNICOMPTA_API_URL'], token=os.environ['PNICOMPTA_API_TOKEN'])
    comptes = await client.list_comptes()
    print(f'{len(comptes)} comptes')
    for numero, libelle in comptes[:5]:
        print(numero, libelle)

asyncio.run(main())
"
```

Run with the real `PNICOMPTA_API_URL`/`PNICOMPTA_API_TOKEN` in the environment (source `.env` as in every prior manual check this session). Expected: a non-empty list of `(numero, libelle)` pairs — categories that have an `account_number` configured (categories without one are silently skipped, matching the filter in Step 1).

- [ ] **Step 3: Commit**

```bash
git add src/comptis/infrastructure/mcp/pnicompta_client.py
git commit -m "feat(mcp): add PniComptaClient.list_comptes() reading PNiCompta categories"
```

---

## Task 6: Extract `build_mcp_client_for_org` into a shared factory

**Files:**
- Create: `src/comptis/infrastructure/mcp/client_factory.py`
- Modify: `src/comptis/interface/api/rapprochement/router.py`

**Interfaces:**
- Produces: `build_mcp_client_for_org(org_id: UUID, session: AsyncSession) -> PniComptaClient | PniComptaMcpClient`
- Consumed by: `rapprochement/router.py` (this task) and Task 7's new admin endpoint

`rapprochement/router.py` currently has a private `_build_mcp_client_for_org` doing exactly this. Task 7 needs the identical logic (resolve an org's configured PNiCompta connection, DB config first, env vars fallback) to build a client for `list_comptes()`. Two real, unrelated call sites needing identical logic — this is genuine duplication, not premature abstraction, so it moves to a shared module both import.

- [ ] **Step 1: Create the shared factory**

Create `src/comptis/infrastructure/mcp/client_factory.py` — this is `_build_mcp_client_for_org`'s current body, moved verbatim and renamed (no logic changes):

```python
from __future__ import annotations

import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.integrations.use_cases import GetDecryptedToken
from comptis.infrastructure.db.integration_repository import (
    FernetTokenCipher,
    SQLAlchemyIntegrationRepository,
)
from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient
from comptis.infrastructure.mcp.pnicompta_mcp_client import PniComptaMcpClient


async def build_mcp_client_for_org(
    org_id: uuid.UUID,
    session: AsyncSession,
) -> PniComptaClient | PniComptaMcpClient:
    """Priorité : config DB → fallback env vars.

    Essaie d'abord de charger la config depuis la DB pour 'pnicompta'.
    Si trouvée et decryptable, l'utilise.
    Sinon, fallback sur les variables d'environnement.
    """
    try:
        cipher = FernetTokenCipher.from_env()
    except KeyError:
        cipher = None
    if cipher is not None:
        repo = SQLAlchemyIntegrationRepository(session, cipher)
        token = await GetDecryptedToken(repo).execute(org_id, "pnicompta")
        integ = await repo.get(org_id, "pnicompta")
        if integ is not None:
            if integ.mcp_url:
                return PniComptaMcpClient(url=integ.mcp_url, api_key=token or "")
            if integ.api_url:
                return PniComptaClient(base_url=integ.api_url, token=token or "")

    # Fallback env vars
    mcp_url = os.environ.get("PNICOMPTA_MCP_URL", "")
    api_key = os.environ.get("PNICOMPTA_API_TOKEN", "")
    if mcp_url:
        return PniComptaMcpClient(url=mcp_url, api_key=api_key)
    base_url = os.environ.get("PNICOMPTA_API_URL", "http://localhost:8000/api")
    return PniComptaClient(base_url=base_url, token=api_key)
```

- [ ] **Step 2: Update `rapprochement/router.py` to use it**

In `src/comptis/interface/api/rapprochement/router.py`:

Remove these two now-unused imports (both were only used inside `_build_mcp_client_for_org`):

```python
from comptis.application.integrations.use_cases import GetDecryptedToken
```

```python
from comptis.infrastructure.db.integration_repository import (
    FernetTokenCipher,
    SQLAlchemyIntegrationRepository,
)
```

Remove the top-level `import os` — after this change nothing else in the file uses `os`.

Add the new import alongside the other `comptis.infrastructure.mcp` import:

```python
from comptis.infrastructure.mcp.client_factory import build_mcp_client_for_org
```

Delete the entire `_build_mcp_client_for_org` function (its whole body, lines 42-72 in the file as it stands before this task):

```python
async def _build_mcp_client_for_org(
    org_id: uuid.UUID,
    session: AsyncSession,
) -> PniComptaClient | PniComptaMcpClient:
    """Priorité : config DB → fallback env vars.
    ...
    """
    ...
    return PniComptaClient(base_url=base_url, token=api_key)
```

And update its one call site inside `run_reconciliation`:

```python
    mcp_client = await _build_mcp_client_for_org(org_id, session)
```

becomes:

```python
    mcp_client = await build_mcp_client_for_org(org_id, session)
```

- [ ] **Step 3: Run the existing reconciliation tests to confirm nothing broke**

```bash
arch -arm64 uv run pytest tests/interface/api/test_rapprochement.py -v -m integration
```

Expected: same pass count as before this task (this is a pure refactor — no behavior change).

- [ ] **Step 4: Commit**

```bash
git add src/comptis/infrastructure/mcp/client_factory.py src/comptis/interface/api/rapprochement/router.py
git commit -m "refactor(mcp): extract build_mcp_client_for_org into a shared factory"
```

---

## Task 7: Admin endpoint — `POST /admin/comptabilite/import-plan-comptable`

**Files:**
- Create: `src/comptis/interface/api/admin/comptabilite/__init__.py`
- Create: `src/comptis/interface/api/admin/comptabilite/schemas.py`
- Create: `src/comptis/interface/api/admin/comptabilite/router.py`
- Modify: `src/comptis/interface/api/main.py`
- Test: `tests/interface/api/test_admin_comptabilite.py`

**Interfaces:**
- Consumes: `ImporterPlanComptable` (Task 2), `SQLAlchemyCompteComptableRepository` (Task 4), `build_mcp_client_for_org` (Task 6), `PniComptaClient` (Task 5), `require_admin`/`get_db_session` (existing, `interface/api/dependencies.py`), `SQLAlchemyTenantRepository` (existing, `infrastructure/db/repositories.py`), `set_tenant_context` (existing, `infrastructure/db/tenant_context.py`)
- Produces: `router` (FastAPI `APIRouter`, prefix `/admin/comptabilite`), `ImportPlanComptableRequest`/`ImportPlanComptableResponse` schemas

**Critical detail:** `require_admin` sets `app.current_organization_id` and `app.current_user_id`, but leaves `app.current_tenant_id` at the nil placeholder (see `dependencies.py`) — it has no reason to know which tenant an admin action targets. The new `comptes_pcg`/`ecritures` RLS policies are keyed on `app.current_tenant_id` specifically. Without an explicit `set_tenant_context(session, tenant_id=...)` call after resolving and validating `body.tenant_id`, every write in this endpoint would silently match zero rows under RLS. This step is **not optional** — it's the same class of bug fixed in migration 0005, caught here before it ships instead of after.

- [ ] **Step 1: Create `__init__.py`**

```bash
mkdir -p src/comptis/interface/api/admin/comptabilite
touch src/comptis/interface/api/admin/comptabilite/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/interface/api/test_admin_comptabilite.py`:

```python
import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_import_plan_comptable_requires_auth(client):
    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
async def test_import_plan_comptable_non_admin_gets_403(client, user_token: str, admin_tenant_id: str):
    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": admin_tenant_id},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
async def test_import_plan_comptable_rejects_tenant_of_another_org(client, admin_token: str):
    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_import_plan_comptable_saves_comptes_for_admin(client, admin_token: str, admin_tenant_id: str, monkeypatch):
    from comptis.infrastructure.mcp import client_factory
    from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient

    async def fake_list_comptes(self):
        return [("625100", "Voyages et déplacements"), ("606400", "Fournitures")]

    monkeypatch.setattr(PniComptaClient, "list_comptes", fake_list_comptes)

    async def fake_build_client(org_id, session):
        return PniComptaClient(base_url="http://unused", token="unused")

    monkeypatch.setattr(client_factory, "build_mcp_client_for_org", fake_build_client)
    monkeypatch.setattr(
        "comptis.interface.api.admin.comptabilite.router.build_mcp_client_for_org", fake_build_client,
    )

    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": admin_tenant_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    numeros = {c["numero"] for c in body["comptes"]}
    assert numeros == {"625100", "606400"}
```

Note on the last test: `monkeypatch.setattr` is applied to both the module-level `client_factory.build_mcp_client_for_org` and the name as imported into the router module — Python binds `from x import y` at import time, so patching only `client_factory.build_mcp_client_for_org` would not affect the router's already-bound reference. Both patches target the same underlying router behavior; this is the standard fix for that gotcha, not two different things being tested.

- [ ] **Step 3: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/interface/api/test_admin_comptabilite.py -v -m integration
```

Expected: `404 Not Found` on all four (route doesn't exist yet).

- [ ] **Step 4: Implement schemas**

Create `src/comptis/interface/api/admin/comptabilite/schemas.py`:

```python
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ImportPlanComptableRequest(BaseModel):
    tenant_id: UUID


class CompteComptableResponse(BaseModel):
    numero: str
    libelle: str
    classe: int


class ImportPlanComptableResponse(BaseModel):
    comptes: list[CompteComptableResponse]
```

- [ ] **Step 5: Implement the router**

Create `src/comptis/interface/api/admin/comptabilite/router.py`:

```python
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.comptabilite.use_cases import ImporterPlanComptable
from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyCompteComptableRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.infrastructure.mcp.client_factory import build_mcp_client_for_org
from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient
from comptis.interface.api.admin.comptabilite.schemas import (
    CompteComptableResponse,
    ImportPlanComptableRequest,
    ImportPlanComptableResponse,
)
from comptis.interface.api.dependencies import get_db_session, require_admin

router = APIRouter(prefix="/admin/comptabilite", tags=["admin-comptabilite"])


@router.post("/import-plan-comptable", response_model=ImportPlanComptableResponse)
async def import_plan_comptable(
    body: ImportPlanComptableRequest,
    org_id: UUID = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ImportPlanComptableResponse:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(body.tenant_id)
    if tenant is None or tenant.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # require_admin leaves app.current_tenant_id at the nil placeholder — comptes_pcg
    # and ecritures RLS is keyed on it directly, so it must be set explicitly here.
    await set_tenant_context(session, tenant_id=body.tenant_id)

    client = await build_mcp_client_for_org(org_id, session)
    if not isinstance(client, PniComptaClient):
        raise HTTPException(
            status_code=400,
            detail="Import du plan comptable non supporté en mode MCP pour cette organisation",
        )

    repo = SQLAlchemyCompteComptableRepository(session)
    comptes = await ImporterPlanComptable(compte_repo=repo, source=client).execute(body.tenant_id)
    return ImportPlanComptableResponse(
        comptes=[
            CompteComptableResponse(numero=c.numero, libelle=c.libelle, classe=c.classe)
            for c in comptes
        ]
    )
```

- [ ] **Step 6: Register the router in `main.py`**

In `src/comptis/interface/api/main.py`, add the import alongside the other admin router:

```python
from comptis.interface.api.admin.comptabilite.router import router as admin_comptabilite_router
```

```python
app.include_router(admin_comptabilite_router)
```

- [ ] **Step 7: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/interface/api/test_admin_comptabilite.py -v -m integration
```

Expected: `4 passed`

- [ ] **Step 8: Commit**

```bash
git add src/comptis/interface/api/admin/comptabilite/ src/comptis/interface/api/main.py tests/interface/api/test_admin_comptabilite.py
git commit -m "feat(interface): add POST /admin/comptabilite/import-plan-comptable"
```

---

## Task 8: Integration point 1 — auto-match creates an écriture

**Files:**
- Modify: `src/comptis/infrastructure/agents/rapprochement/nodes/match.py`
- Modify: `src/comptis/infrastructure/agents/rapprochement/graph.py`
- Modify: `src/comptis/interface/api/rapprochement/router.py`
- Test: `tests/infrastructure/agents/rapprochement/test_graph.py`

**Interfaces:**
- Consumes: `CreerEcritureDepuisMatch` (Task 2), `SQLAlchemyEcritureRepository` (Task 4)
- Produces: `make_match_node(mcp_client, memory, arbiter, ecriture_repo)` (new 4th param), `build_reconciliation_graph(mcp_client, memory, ecriture_repo, arbiter=None)` (`ecriture_repo` inserted before the existing optional `arbiter`)

This is the auto-match path — the session used to build `mcp_client`/`memory` in `run_reconciliation` already has `app.current_tenant_id` set (from the existing `set_tenant_context(session, organization_id=org_id, tenant_id=body.tenant_id, user_id=user_id)` call already in that function), so no additional context-setting is needed here, unlike Task 7 and Task 9.

- [ ] **Step 1: Update the failing tests first — `test_graph.py`'s 3 existing calls plus one new assertion**

`build_reconciliation_graph`'s signature is changing (`ecriture_repo` inserted as a new required positional parameter before `arbiter`), so every existing call in this file must be updated in the same commit or the whole test module breaks. Replace the full contents of `tests/infrastructure/agents/rapprochement/test_graph.py`:

```python
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

    async def mark_rapprochement(self, facture_id, transaction_id, statut, amount):
        self.marked.append((facture_id, transaction_id, statut, amount))


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


class FakeEcritureRepository:
    def __init__(self):
        self.saved = []

    async def save(self, ecriture):
        self.saved.append(ecriture)


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
    ecriture_repo = FakeEcritureRepository()
    arbiter = FakeArbiter(confidence=0.0)

    graph = build_reconciliation_graph(mcp, memory, ecriture_repo, arbiter)
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

    # The confirmed match must have produced a persisted écriture
    assert len(ecriture_repo.saved) == 1
    ecriture = ecriture_repo.saved[0]
    assert ecriture.tenant_id == tenant_id
    assert ecriture.transaction_id == "t1"
    assert ecriture.facture_id == "f1"
    assert ecriture.montant == Decimal("100.00")
    assert ecriture.compte_id is None


@pytest.mark.asyncio
async def test_unmatched_when_no_candidates():
    tenant_id = uuid4()
    t = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="UNKNOWN")
    # Facture with very different amount — won't pass prefilter
    f = Facture(id="f1", montant=Decimal("500.00"), date=date(2026, 1, 15),
                fournisseur="AUTRE", statut_rapprochement="non_rapprochee")

    mcp = FakeMcp(transactions=[t], factures=[f])
    memory = FakeMemory()
    ecriture_repo = FakeEcritureRepository()
    arbiter = FakeArbiter(confidence=0.0)

    graph = build_reconciliation_graph(mcp, memory, ecriture_repo, arbiter)
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
    assert len(ecriture_repo.saved) == 0


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
    ecriture_repo = FakeEcritureRepository()
    arbiter = FakeArbiter(confidence=0.0)

    graph = build_reconciliation_graph(mcp, memory, ecriture_repo, arbiter)
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
    assert len(ecriture_repo.saved) == 1
```

- [ ] **Step 2: Run to see them fail**

```bash
arch -arm64 uv run pytest tests/infrastructure/agents/rapprochement/test_graph.py -v
```

Expected: `TypeError: build_reconciliation_graph() missing 1 required positional argument: 'arbiter'` (or similar — the call sites now pass 4 positional args to a 3-arg function)

- [ ] **Step 3: Update `match.py`**

In `src/comptis/infrastructure/agents/rapprochement/nodes/match.py`, add the import:

```python
from comptis.application.comptabilite.use_cases import CreerEcritureDepuisMatch
```

Change the function signature:

```python
def make_match_node(
    mcp_client: McpClient,
    memory: ReconciliationMemory,
    arbiter: LLMArbiter,
    ecriture_repo,
):
```

At the first `mark_rapprochement` call site (inside the memory-pattern branch), immediately after the existing line

```python
                        await mcp_client.mark_rapprochement(best.id, txn.id, statut, amount=abs(txn.montant))
```

insert:

```python
                        await CreerEcritureDepuisMatch(ecriture_repo).execute(
                            tenant_id=tenant_id,
                            transaction_id=txn.id,
                            facture_id=best.id,
                            montant=abs(txn.montant),
                            date_=txn.date,
                        )
```

At the second call site (main scoring branch), immediately after

```python
                await mcp_client.mark_rapprochement(best_facture.id, txn.id, statut, amount=abs(txn.montant))
```

insert:

```python
                await CreerEcritureDepuisMatch(ecriture_repo).execute(
                    tenant_id=tenant_id,
                    transaction_id=txn.id,
                    facture_id=best_facture.id,
                    montant=abs(txn.montant),
                    date_=txn.date,
                )
```

At the third call site (LLM gray-zone branch), immediately after

```python
                    await mcp_client.mark_rapprochement(best_facture.id, txn.id, statut, amount=abs(txn.montant))
```

insert:

```python
                    await CreerEcritureDepuisMatch(ecriture_repo).execute(
                        tenant_id=tenant_id,
                        transaction_id=txn.id,
                        facture_id=best_facture.id,
                        montant=abs(txn.montant),
                        date_=txn.date,
                    )
```

(Indentation matters — each insertion matches the indentation of the `mark_rapprochement` line immediately above it, since they're at three different nesting depths in the function.)

- [ ] **Step 4: Update `graph.py`**

In `src/comptis/infrastructure/agents/rapprochement/graph.py`, change:

```python
def build_reconciliation_graph(
    mcp_client: McpClient,
    memory: ReconciliationMemory,
    arbiter: LLMArbiter | None = None,
):
```

to:

```python
def build_reconciliation_graph(
    mcp_client: McpClient,
    memory: ReconciliationMemory,
    ecriture_repo,
    arbiter: LLMArbiter | None = None,
):
```

And change:

```python
    match = make_match_node(mcp_client, memory, arbiter)
```

to:

```python
    match = make_match_node(mcp_client, memory, arbiter, ecriture_repo)
```

- [ ] **Step 5: Wire it in `run_reconciliation`**

In `src/comptis/interface/api/rapprochement/router.py`, add the import:

```python
from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyEcritureRepository
```

In `run_reconciliation`, right after the existing line

```python
    memory = SQLAlchemyReconciliationPatternRepository(session)
```

insert:

```python
    ecriture_repo = SQLAlchemyEcritureRepository(session)
```

And change:

```python
    graph = build_reconciliation_graph(mcp_client, memory)  # type: ignore[arg-type]
```

to:

```python
    graph = build_reconciliation_graph(mcp_client, memory, ecriture_repo)  # type: ignore[arg-type]
```

- [ ] **Step 6: Run to see them pass**

```bash
arch -arm64 uv run pytest tests/infrastructure/agents/rapprochement/test_graph.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Run the full non-integration suite to catch anything else this signature change touched**

```bash
arch -arm64 uv run pytest -v -m "not integration"
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/comptis/infrastructure/agents/rapprochement/nodes/match.py src/comptis/infrastructure/agents/rapprochement/graph.py src/comptis/interface/api/rapprochement/router.py tests/infrastructure/agents/rapprochement/test_graph.py
git commit -m "feat(rapprochement): auto-confirmed matches create a persisted écriture"
```

---
