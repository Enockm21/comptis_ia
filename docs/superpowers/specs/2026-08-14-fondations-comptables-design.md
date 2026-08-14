# Fondations comptables — Spec de conception

**Date :** 2026-08-14
**Auteur :** Enock Maya
**Brique :** SP3 — Fondations comptables (1/3 : plan de comptes + écritures)
**Statut :** Approuvé pour implémentation

---

## Contexte

Jusqu'ici, Comptis ne persiste aucune donnée comptable : le rapprochement tourne
entièrement en mémoire le temps d'un run (`_runs`, un dict Python), et rien ne
survit à un redémarrage du serveur côté Comptis. PNiCompta reste la seule
source de données (transactions bancaires, factures fournisseurs).

Décision de positionnement produit (voir discussion du 2026-08-13, informée par
une analyse de marché — Pennylane domine avec 800k clients et 6000+ cabinets
partenaires après une levée de 175M€ en janvier 2026) : **Comptis devient son
propre système de référence comptable** ("Option A"), pas une couche IA qui
écrit dans un logiciel tiers. PNiCompta reste une source de données brutes
(trésorerie), Comptis construit sa propre compta par-dessus, jusqu'au bilan à
terme.

Cette brique pose les fondations : un plan de comptes PCG possédé par Comptis,
et une "écriture" qui matérialise durablement chaque transaction rapprochée.
Aucune logique de catégorisation intelligente ni interface de revue — ce sont
les briques SP4 (moteur de catégorisation) et SP5 (UI de revue) qui viendront
se brancher dessus, sans migration supplémentaire.

Cible de test réelle : SAS Planet Network International (l'organisation
utilisée pour tous les tests du rapprochement), avec l'intention de valider le
mapping de comptes avec leur expert-comptable avant d'aller plus loin.

---

## Périmètre

### Inclus
- Plan de comptes (`comptes_pcg`) possédé par Comptis, par tenant, importé
  initialement depuis les `Category` déjà configurées côté PNiCompta
  (`GET /categories/` — chaque catégorie porte déjà un `account_number` et un
  `account_label` réels, configurés par l'expert-comptable du client).
- Écriture comptable (`ecritures`) créée automatiquement à chaque rapprochement
  confirmé (auto-match à score ≥ 0.85, ou confirmation humaine via
  `POST /run/{id}/resolve`), avec compte vide (`compte_id = NULL`) et statut
  `a_categoriser`.
- Deux points d'intégration dans le code existant du rapprochement (voir
  Bloc C), aucun autre déclencheur.

### Explicitement hors périmètre
- **Côté clients / recettes** (comptes 411/7xx) — le Grand Livre clients de
  Planet Network International vient d'un logiciel distinct ("SYGNATURES"),
  pas de PNiCompta. Pas de connecteur pour ça aujourd'hui ; brique séparée à
  spécifier plus tard si nécessaire.
- **Partie double** (compte débité / compte crédité) — une écriture porte un
  seul compte pour l'instant. La partie double sera introduite quand la brique
  grand livre/balance sera spécifiée, en faisant évoluer cette table plutôt
  qu'en la remplaçant.
- **Moteur de catégorisation** (proposer automatiquement le bon compte) —
  brique SP4. Cette brique-ci laisse `compte_id` à `NULL` systématiquement.
- **Interface de revue** — brique SP5. Aucune UI dans cette brique.
- **Lettrage** — le mécanisme formel de rapprochement facture/règlement en
  comptabilité française (voir Grand Livre clients). Noté pour une brique
  ultérieure quand la partie double sera modélisée ; pas nécessaire tant que
  l'écriture ne porte qu'un compte.

---

## Bloc A — Entités du domaine

Nouveau module `domain/comptabilite/`, suivant exactement le style déjà en
place dans `domain/tenancy/` et `domain/rapprochement/` (dataclasses pures,
zéro dépendance framework).

`domain/comptabilite/value_objects.py` :

```python
from enum import StrEnum


class StatutEcriture(StrEnum):
    A_CATEGORISER = "a_categoriser"  # compte_id est NULL — seul statut atteint par cette brique
    CATEGORISEE = "categorisee"      # compte proposé par le moteur (brique SP4)
    VALIDEE = "validee"              # confirmée par un humain (brique SP5)
```

`domain/comptabilite/entities.py` :

```python
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
    numero: str      # ex: "625100" — alphanumérique accepté (PNiCompta utilise
                      # aussi des codes mnémoniques comme "CARCEP" côté clients,
                      # donc `numero` reste une string, jamais un int)
    libelle: str      # ex: "Voyages et déplacements"
    classe: int        # premier chiffre du numéro (6 = charges, 7 = produits, etc.)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Ecriture:
    tenant_id: UUID
    transaction_id: str        # id PNiCompta de la transaction bancaire
    facture_id: str            # id PNiCompta de la facture fournisseur liée
    montant: Decimal
    date: date_
    compte_id: UUID | None = None
    statut: StatutEcriture = StatutEcriture.A_CATEGORISER
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
```

`classe` se dérive du premier caractère de `numero` au moment de la création
(`int(numero[0])` si `numero[0].isdigit()`, sinon la classe est laissée à
l'appelant — un code mnémonique comme "CARCEP" n'a pas de classe PCG directe,
mais ce cas n'apparaît pas côté fournisseurs, seulement côté clients, hors
périmètre).

---

## Bloc B — Import initial + persistance

### Ports (`application/comptabilite/ports.py`)

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

### Use cases (`application/comptabilite/use_cases.py`)

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

### Persistance (infrastructure)

Deux nouvelles tables, migration `0006_add_comptabilite_tables.py`, RLS scoped
sur `app.current_tenant_id` (le même GUC que `run_reconciliation` pose déjà
correctement depuis le correctif du 2026-08-13 — pas de nouveau risque
d'oubli de GUC comme celui qu'on a rencontré sur `reconciliation_patterns`).

```sql
CREATE TABLE comptes_pcg (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    numero VARCHAR(20) NOT NULL,
    libelle VARCHAR(255) NOT NULL,
    classe INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, numero)
);

CREATE TABLE ecritures (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    transaction_id VARCHAR(64) NOT NULL,
    facture_id VARCHAR(64) NOT NULL,
    montant NUMERIC(12, 2) NOT NULL,
    date DATE NOT NULL,
    compte_id UUID NULL REFERENCES comptes_pcg(id) ON DELETE SET NULL,
    statut VARCHAR(20) NOT NULL DEFAULT 'a_categoriser',
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, transaction_id)
);

ALTER TABLE comptes_pcg ENABLE ROW LEVEL SECURITY;
ALTER TABLE comptes_pcg FORCE ROW LEVEL SECURITY;
CREATE POLICY comptes_pcg_tenant_isolation ON comptes_pcg
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE ecritures ENABLE ROW LEVEL SECURITY;
ALTER TABLE ecritures FORCE ROW LEVEL SECURITY;
CREATE POLICY ecritures_tenant_isolation ON ecritures
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON comptes_pcg TO comptis_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ecritures TO comptis_app;
```

`UNIQUE (tenant_id, transaction_id)` empêche qu'une même transaction génère
deux écritures si le run est rejoué — `save()` doit gérer ce cas en upsert
silencieux (`ON CONFLICT DO NOTHING`), pas en erreur, puisqu'un run peut
légitimement retraiter une transaction déjà passée en écriture.

`SQLAlchemyCompteComptableRepository` et `SQLAlchemyEcritureRepository` dans
`infrastructure/db/comptabilite_repository.py`, même style que
`SQLAlchemyReconciliationPatternRepository`.

### Import depuis PNiCompta

Nouvelle méthode sur `PniComptaClient` (implémente `PlanComptableSource`) :

```python
async def list_categories(self) -> list[tuple[str, str]]:
    data = await self._get("/categories/", {"page_size": 500})
    rows = data.get("results", data) if isinstance(data, dict) else data
    return [
        (r["account_number"], r.get("account_label") or r.get("name", ""))
        for r in rows
        if r.get("account_number")  # ignore les catégories sans compte PCG configuré
    ]
```

`ImporterPlanComptable` est déclenché manuellement (pas d'automatisation dans
cette brique), mais suit le même principe que le reste du projet : exposé via
un endpoint admin, pas un script à part. `POST /admin/comptabilite/import-plan-comptable`,
`require_admin` (même dépendance que `/admin/integrations`), sans body — utilise
l'org de l'admin connecté pour résoudre `tenant_id` et appelle
`ImporterPlanComptable.execute(tenant_id)`. Suffisant pour importer et valider
le plan de comptes de Planet Network International avec leur expert-comptable ;
aucune UI ne l'appelle dans cette brique, mais l'action reste testable et
rejouable comme toute autre route admin.

---

## Bloc C — Points d'intégration

Deux endroits créent un `Match` aujourd'hui — les deux appellent désormais
`CreerEcritureDepuisMatch` juste après.

**1. Auto-match** (`infrastructure/agents/rapprochement/nodes/match.py`) —
les 3 sites qui appellent `mcp_client.mark_rapprochement(...)` (voir le
correctif du paramètre `amount` du 2026-08-13). `make_match_node` reçoit un
paramètre supplémentaire `ecriture_repo: EcritureRepository`, construit et
injecté dans `run_reconciliation` (`interface/api/rapprochement/router.py`)
exactement comme `memory` (`SQLAlchemyReconciliationPatternRepository(session)`)
l'est déjà — même session, même transaction.

**2. Confirmation humaine** (`resolve_conflict`, même fichier router) —
quand `decision == "confirmer"` ou `"ecart_accepte"`, juste après la
construction du `Match` ajouté à `matches`. La `session` FastAPI est déjà
disponible dans ce handler.

Dans les deux cas, `tenant_id` vient de `run["tenant_id"]` (déjà présent dans
l'état du run), `transaction_id`/`facture_id` du `Match` lui-même,
`montant` = `abs(txn.montant)` (même convention que le score et
`mark_rapprochement`, cohérent avec le correctif de signe du 2026-08-13),
`date` = `txn.date`.

---

## Bloc D — Stratégie de test

Même pattern que le reste du repo :
- **Domaine** : `CompteComptable`/`Ecriture` — valeurs par défaut, dérivation
  de `classe` depuis `numero`.
- **Application** : `ImporterPlanComptable` et `CreerEcritureDepuisMatch` avec
  des fakes en mémoire (`FakeCompteComptableRepository`,
  `FakeEcritureRepository`, `FakePlanComptableSource`).
- **Infrastructure** (`@pytest.mark.integration`, testcontainers) :
  - Isolation RLS sur `comptes_pcg` et `ecritures` — un tenant ne voit pas les
    comptes/écritures d'un autre (même test que `test_isolation.py` existant).
  - `UNIQUE (tenant_id, transaction_id)` — rejouer la création d'écriture pour
    la même transaction ne crée pas de doublon.
- **Intégration bout en bout** : un run de rapprochement avec un match
  auto-confirmé produit bien une écriture `a_categoriser` en base ; une
  confirmation humaine via `POST /resolve` aussi.
- **Interface** (`@pytest.mark.integration`, httpx) :
  `POST /admin/comptabilite/import-plan-comptable` — 401 sans token, 403 pour
  un non-admin (mêmes cas que `test_admin_integrations.py`), 200 et comptes
  effectivement créés pour un admin, avec un `PlanComptableSource` fake
  injecté via `app.dependency_overrides`.

Pas de test contre la vraie API PNiCompta dans la suite automatisée — 
`list_categories()` est vérifié par un test d'intégration avec un
`PlanComptableSource` fake, la validation contre les vraies données de Planet
Network International se fait manuellement (comme pour le rapprochement).

---

## Stack technique

| Couche | Techno |
|---|---|
| Backend | Python 3.12, SQLAlchemy async, Alembic (RLS existante réutilisée) |
| Import initial | `PniComptaClient.list_categories()` — nouvelle méthode, même client HTTP |

---

## Séquence d'implémentation

1. Domaine : `value_objects.py`, `entities.py`.
2. Application : `ports.py`, `use_cases.py`, tests avec fakes.
3. Infrastructure : migration `0006`, modèles ORM, repositories, tests RLS.
4. `PniComptaClient.list_categories()`.
5. Points d'intégration : `match.py` (3 sites) + `resolve_conflict`, tests
   d'intégration bout en bout.
6. Import manuel du plan de comptes de Planet Network International, à
   valider avec leur expert-comptable avant la brique SP4.
