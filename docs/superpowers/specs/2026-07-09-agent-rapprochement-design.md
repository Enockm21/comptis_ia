# Agent Rapprochement — Design Spec

**Date :** 2026-07-09
**Auteur :** Enock Maya
**Brique :** 3 / 7 (après API Gateway)

---

## Contexte

Comptis est un agent comptable IA pour PME françaises. L'Agent Rapprochement est le premier agent métier : il rapproche automatiquement les transactions bancaires (venant de Bridge via PNiCompta) avec les factures (uploadées manuellement ou récupérées automatiquement dans PNiCompta).

L'agent lit PNiCompta directement via MCP — aucun stockage S3 intermédiaire.

---

## Périmètre

**Inclus :**
- State machine LangGraph explicite : fetch → match → human_review → report
- Pré-filtre déterministe (montant ±10%, date ±30j)
- Scoring composite fuzzy (`rapidfuzz`) sans LLM
- LLM en fallback uniquement sur la zone grise (score 50–85%)
- Mémoire des patterns (table Postgres, RLS multi-tenant)
- Bootstrap de la mémoire depuis les rapprochements existants dans PNiCompta
- Human-in-the-loop via LangGraph interrupt + endpoint de résolution
- Rapport final : rapprochées ✅ / non rapprochées ❌ / écarts ⚠️

**Hors périmètre :**
- Interface utilisateur (frontend React — brique future)
- Export FEC (Agent Export FEC — brique future)
- Surveillance Bridge vs relevés (Agent Surveillance — brique future)
- Embeddings vectoriels / pgvector (évolution post-MVP)

---

## Architecture

### Couches (Clean Architecture)

```
domain/
  rapprochement/
    entities.py        → Facture, Transaction, Match, Conflict, ReconciliationPattern
    value_objects.py   → MatchStatut, ConflictRaison

application/
  rapprochement/
    ports.py           → Protocol : ReconciliationMemory, ReconciliationReporter
    use_cases.py       → RunReconciliation (orchestrateur haut niveau)

infrastructure/
  agents/
    rapprochement/
      graph.py         → définition LangGraph (nœuds + edges)
      nodes/
        fetch.py       → list_transactions + list_factures via MCP
        match.py       → pré-filtre + scoring + routage
        human_review.py → interrupt + réception décision
        report.py      → génération rapport final
      scorer.py        → score composite fuzzy (rapidfuzz)
      llm_arbiter.py   → LLM fallback (zone grise 50–85%)
  db/
    reconciliation_patterns.py  → SQLAlchemy repo pour patterns
    migrations/versions/
      0003_add_reconciliation_patterns.py

interface/
  api/
    rapprochement/
      router.py        → POST /reconciliation/run, POST /reconciliation/{run_id}/resolve
      schemas.py       → RunRequest, ResolveRequest, ReconciliationReport
```

### Règle de dépendance

```
interface → application → domain
interface → infrastructure
application → domain
infrastructure/agents/ → domain (entities uniquement)
```

`application/rapprochement/` ne connaît ni LangGraph ni SQLAlchemy.

---

## Modèle de données

### Entités domaine

```python
@dataclass
class Facture:
    id: str
    montant: Decimal
    date: date
    fournisseur: str
    statut_rapprochement: Literal["rapprochee", "non_rapprochee", "ecart"]
    transaction_id: str | None = None

@dataclass
class Transaction:
    id: str
    montant: Decimal
    date: date
    libelle: str
    facture_id: str | None = None

@dataclass
class Match:
    facture_id: str
    transaction_id: str
    confidence: float
    ecart_montant: Decimal
    statut: Literal["confirme", "ecart"]

@dataclass
class Conflict:
    transaction: Transaction
    facture: Facture | None
    raison: Literal["confidence_insuffisante", "ecart_montant"]
    composite_score: float

@dataclass
class ReconciliationPattern:
    id: UUID
    tenant_id: UUID
    libelle_pattern: str      # normalisé (uppercase, stripped)
    fournisseur: str
    montant_approx: Decimal
    occurrence_count: int
    last_seen_at: datetime
```

### Migration 0003 — table `reconciliation_patterns`

```sql
CREATE TABLE reconciliation_patterns (
    id              UUID PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    libelle_pattern VARCHAR(255) NOT NULL,
    fournisseur     VARCHAR(255) NOT NULL,
    montant_approx  NUMERIC(12, 2) NOT NULL,
    occurrence_count INT NOT NULL DEFAULT 1,
    last_seen_at    TIMESTAMPTZ NOT NULL,
    UNIQUE (tenant_id, libelle_pattern, fournisseur)
);

CREATE INDEX ix_reconciliation_patterns_tenant_libelle
    ON reconciliation_patterns (tenant_id, libelle_pattern);

ALTER TABLE reconciliation_patterns ENABLE ROW LEVEL SECURITY;

CREATE POLICY rp_org_isolation ON reconciliation_patterns
    USING (
        tenant_id IN (
            SELECT id FROM tenants
            WHERE organization_id = current_setting('app.organization_id', true)::uuid
        )
    );

GRANT SELECT, INSERT, UPDATE, DELETE ON reconciliation_patterns TO comptis_app;
```

---

## State machine LangGraph

### State

```python
class ReconciliationState(TypedDict):
    tenant_id: UUID
    transactions: list[Transaction]       # chargées depuis PNiCompta
    factures: list[Facture]               # chargées depuis PNiCompta
    matches: list[Match]                  # rapprochements confirmés
    pending_review: list[Conflict]        # attente décision humaine
    unmatched: list[Transaction]          # aucune facture candidate trouvée
    report: ReconciliationReport | None
```

### Graphe

```
fetch ──→ match ──→ (routing conditionnel)
                      ├── direct confirm  ──→ match (transaction suivante)
                      ├── human_review    ──→ match (après décision)
                      ├── unmatched       ──→ match (transaction suivante)
                      └── toutes traitées ──→ report
```

### Nœuds

**`fetch`**
- Bootstrap mémoire : `list_transactions(statut="rapprochee")` + `list_factures(statut="rapprochee")` → upsert patterns
- Charge données courantes : `list_transactions(statut="non_rapprochee")` + `list_factures(statut="non_rapprochee")`

**`match`** (par transaction)
1. Lookup mémoire : pattern connu pour ce libellé ?
   - Pattern trouvé (occurrence_count ≥ 3) → boost score → si ≥ 0.85 → confirmer directement
2. Pré-filtre candidats :
   - `montant dans [t.montant × 0.90, t.montant × 1.10]`
   - `date dans [t.date − 30j, t.date + 30j]`
   - `statut_rapprochement == "non_rapprochee"`
3. Score composite sur chaque candidat :
   - `text_score = fuzz.token_sort_ratio(t.libelle, f.fournisseur) / 100`
   - `amount_score = max(0, 1 − abs(t.montant − f.montant) / t.montant)`
   - `date_score = max(0, 1 − abs((t.date − f.date).days) / 30)`
   - `composite = 0.40 × text + 0.35 × amount + 0.25 × date`
4. Routage :
   - composite ≥ 0.85 → `mark_rapprochement` + upsert pattern → transaction suivante
   - 0.50 ≤ composite < 0.85 → LLM arbiter → si LLM confirme (≥ 0.85) → confirmer ; sinon → human_review
   - composite < 0.50 → unmatched
   - 0 candidats après pré-filtre → unmatched

**`human_review`**
- `interrupt_before("human_review")` — suspend, sauvegarde state via **LangGraph Postgres checkpointer** (table `langgraph_checkpoints`, créée par LangGraph)
- L'API notifie l'opérateur (liste des conflits en attente)
- `POST /reconciliation/{run_id}/resolve` reprend le graph depuis le checkpoint avec la décision

**`report`**
- Agrège matches + unmatched + conflicts résolus
- Retourne `ReconciliationReport` : totaux + liste détaillée par statut

---

## MCP Tools

Interface entre l'agent et PNiCompta :

```python
list_transactions(statut?: str) → list[Transaction]
get_transaction(id: str) → Transaction
list_factures(statut?: str) → list[Facture]
get_facture(id: str) → Facture
add_facture(data: dict) → Facture
mark_rapprochement(facture_id: str, transaction_id: str, statut: str) → None
```

---

## Configuration

```env
RECONCILIATION_CONFIDENCE_THRESHOLD=0.85   # seuil confirm direct
RECONCILIATION_LLM_LOWER_BOUND=0.50        # en dessous → unmatched direct
PATTERN_MIN_OCCURRENCES=3                  # nb de confirmations avant boost automatique
LLM_MODEL=claude-sonnet-5
PNICOMPTA_MCP_URL=...
```

---

## Endpoints API

```
POST /reconciliation/run
  body: { tenant_id }
  → démarre un run LangGraph, retourne { run_id }

GET /reconciliation/{run_id}/conflicts
  → liste les conflits en attente de décision humaine

POST /reconciliation/{run_id}/resolve
  body: { conflict_id, decision: "confirmer" | "rejeter" | "ecart_accepte" }
  → reprend le graph depuis le state sauvegardé

GET /reconciliation/{run_id}/report
  → rapport final si le run est terminé
```

---

## Tests

### Unitaires (sans DB, sans LLM, sans MCP)

- `test_scorer.py`
  - score exact (même libellé, même montant, même date) → 1.0
  - montant à +8% → amount_score réduit
  - date à 25j d'écart → date_score réduit
  - libellé très différent → text_score bas

- `test_pattern_store.py`
  - upsert nouveau pattern → occurrence_count = 1
  - upsert même pattern → occurrence_count += 1
  - lookup pattern inexistant → None

### Intégration (testcontainers Postgres + MCP fakes)

- `test_matching_node.py` — vérifie routage correct (confirm direct / human_review / unmatched)
- `test_memory_bootstrap.py` — bootstrap depuis transactions déjà rapprochées
- `test_human_review.py` — interrupt → resolve → reprise → match confirmé
- `test_full_run.py` — bout-en-bout : 5 transactions (2 directes, 1 écart, 1 LLM, 1 unmatched) → rapport correct

---

## Stack technique

**Nouveaux packages :**

```toml
langgraph>=0.2
langchain-anthropic>=0.2
rapidfuzz>=3.9
```

**Existant réutilisé :** FastAPI, SQLAlchemy async, testcontainers, pytest-asyncio

---

## Ce qui vient après

- **Agent Surveillance** : vérifie cohérence entre données Bridge et relevés bancaires uploadés
- **Agent Contrôle** : valide que les rapprochements produits sont cohérents
- **Agent Export FEC** : prépare le fichier FEC à partir des données rapprochées
- **Frontend React** : interface opérateur pour human review + dashboard
