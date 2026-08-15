# PCG Categorization — Design Spec

**Date :** 2026-08-15
**Auteur :** Enock Maya
**Brique :** Catégorisation comptable automatique (PCG)
**Statut :** Approuvé pour implémentation

---

## Contexte

Cette brique matérialise **ADR-002** d'`ARCHITECTURE.md` (RAG hybride sur le Plan Comptable
Général) et s'inscrit dans COUCHE 4 (Agent Runtime) : le maillon `Categorize` du pipeline
`Classify → Extract → Score → Categorize → Reconcile → Human Review`.

Elle est indépendante du module `rapprochement` déjà codé (qui matche transaction bancaire ↔
facture) : la catégorisation répond à une question différente — *quel compte du Plan Comptable
Général correspond à cette écriture ?* — en amont ou en parallèle du rapprochement.

Le projet est validé sur un tenant pilote réel (l'entreprise du porteur du projet), pour lequel
un historique d'écritures comptables réelles (libellé → compte réellement utilisé par le
comptable) est disponible localement pour construire un jeu d'évaluation supervisé : deux
exercices fiscaux complets au format **FEC** (Fichier des Écritures Comptables, export officiel
obligatoire — cf. article A47 A-1 du LPF), qui donnent le vrai code PCG (`CompteNum`) apparié
directement à chaque libellé d'écriture. Ces exports restent hors dépôt git — ils ne servent qu'à
l'évaluation locale de la précision, jamais committés (le projet est open source et public).

**Note sur le format des codes comptes :** les `CompteNum` réels du tenant pilote sont
zero-paddés sur 8 chiffres (ex. `62610000`), alors que la racine PCG officielle fait 6 chiffres
(`626100`). Le référentiel `comptes_pcg` seedé par cette brique stocke la racine 6 chiffres
uniquement ; toute comparaison avec un `CompteNum` réel du FEC doit normaliser en ne comparant
que les 6 premiers caractères. C'est une approximation "au niveau famille" assumée : certains
codes réels du tenant portent une précision de sous-compte au-delà de la racine à 6 chiffres
(ex. `66116300` vs `66116400` sont deux sous-comptes réellement distincts, pas juste un
padding) — non couverte par cette première itération.

---

## Périmètre

### Inclus
- Entités domain : `CompteComptable`, `EcritureACategoriser`, `CategorizationPattern`,
  `CategorizationSuggestion`, `CategorizationDecision`
- Use cases : `CategorizeEcriture`, `ValidateCategorization`
- Repository pattern par tenant (apprentissage incrémental, calqué sur
  `ReconciliationPattern` existant)
- Port `AccountRetriever` + **implémentation phase 1** : recherche fuzzy (rapidfuzz, déjà une
  dépendance du projet) contre une table `comptes_pcg` en Postgres. Le repo n'a aujourd'hui
  aucune dépendance RAG (pas de vector store, pas de provider d'embeddings, pas de reranker) —
  construire le RAG hybride complet (dense + BM25 + reranking) en même temps que les couches
  domain/application serait un sous-système à part entière. Le port `AccountRetriever` est conçu
  pour que cette implémentation soit remplaçable sans toucher aux use cases : la brique RAG
  hybride (ADR-002 complet) est reportée à une itération suivante, une fois le harness
  d'évaluation (niveau 4 ci-dessous) validé avec des métriques réelles sur le fuzzy matching.
- Seuil de confiance configurable (défaut 85%, cohérent avec la contrainte non négociable
  #3 d'ARCHITECTURE.md) déclenchant l'escalade vers Human Review
- Seuil d'occurrences avant qu'un pattern tenant soit jugé fiable (défaut **3**, configurable)
- Harness d'évaluation contre l'historique réel du tenant pilote (hors dépôt, local uniquement)

### Explicitement hors périmètre
- **Ingestion / OCR** : l'entrée de cette brique est une ligne d'écriture déjà saisie
  (libellé + montant + tiers), pas un PDF/email brut. L'extraction depuis un document source
  reste une brique séparée (COUCHE 3 Ingestion).
- **Rapprochement bancaire** : reste dans le module `rapprochement` existant, non touché ici.
- **Endpoints API exposant ces use cases** : `interface/api/categorization/` sera ajouté dans
  cette brique en suivant le patron déjà établi (`rapprochement/router.py`), mais l'auth/API
  Gateway au niveau Organization reste la responsabilité de la brique `organizations` en cours.
- **Gouvernance du référentiel PCG** : mise à jour du corpus (nouveaux comptes, PCG révisé)
  non traitée ici.
- **RAG hybride complet** (Qdrant, embeddings denses, index BM25, cross-encoder reranker) :
  reporté à une brique suivante. Voir note de phasage dans "Inclus" ci-dessus.

---

## Architecture — Clean Architecture en couches

```
domain/categorization/        ← zéro dépendance framework
application/categorization/   ← dépend de domain uniquement (ports = Protocols)
infrastructure/                ← implémente les ports (SQLAlchemy, Qdrant, BM25, reranker)
interface/api/categorization/ ← router FastAPI, schemas Pydantic
```

---

## Modèle de données

### Entités domain (`domain/categorization/entities.py`)

```python
@dataclass
class CompteComptable:
    code: str            # ex. "626100"
    libelle: str          # ex. "Frais de télécommunications"
    classe: int            # 1-7, classe PCG

@dataclass
class EcritureACategoriser:
    id: UUID
    libelle: str
    montant: Decimal
    tiers: str
    date: date

@dataclass
class CategorizationPattern:
    tenant_id: UUID
    libelle_pattern: str
    fournisseur: str
    compte_code: str
    occurrence_count: int
    last_seen_at: datetime
    id: UUID = field(default_factory=uuid4)

@dataclass
class CategorizationSuggestion:
    compte_code: str
    confidence: float               # 0.0 - 1.0
    source: CategorizationSource     # PATTERN | RAG
    evidence: list[str]              # libellés/comptes retenus — audit trail

@dataclass
class CategorizationDecision:
    id: UUID
    tenant_id: UUID                  # requis pour la policy RLS — sans lui rien à filtrer
    ecriture_id: UUID
    compte_code: str
    statut: CategorizationStatut     # AUTO_VALIDATED | PENDING_REVIEW | HUMAN_VALIDATED
    confidence: float
    validated_by: UUID | None        # None si auto-validé
    created_at: datetime
```

### Value objects (`domain/categorization/value_objects.py`)

```python
class CategorizationSource(StrEnum):
    PATTERN = "pattern"
    RAG = "rag"

class CategorizationStatut(StrEnum):
    AUTO_VALIDATED = "auto_validated"
    PENDING_REVIEW = "pending_review"
    HUMAN_VALIDATED = "human_validated"
```

**Contrainte DB :** `UNIQUE (tenant_id, libelle_pattern, fournisseur)` sur
`categorization_patterns` — même contrainte que `reconciliation_patterns`.

---

## Ports (`application/categorization/ports.py`)

```python
class CategorizationPatternRepository(Protocol):
    async def find_by_libelle(
        self, tenant_id: UUID, libelle_pattern: str
    ) -> CategorizationPattern | None: ...
    async def upsert(self, pattern: CategorizationPattern) -> CategorizationPattern: ...

class AccountRetriever(Protocol):
    """Abstrait le RAG hybride (dense + BM25 + rerank) sur le référentiel PCG."""
    async def search(self, query: str, top_k: int = 5) -> list[CategorizationSuggestion]: ...

class CategorizationDecisionRepository(Protocol):
    async def save(self, decision: CategorizationDecision) -> None: ...
    async def get_by_ecriture(self, ecriture_id: UUID) -> CategorizationDecision | None: ...
```

---

## Flux de décision

### `CategorizeEcriture` use case

```
1. Normaliser le libellé de l'écriture (même normalisation que rapprochement,
   à factoriser si la logique converge)
2. pattern = CategorizationPatternRepository.find_by_libelle(tenant_id, libelle_pattern)
3. SI pattern trouvé ET pattern.occurrence_count >= min_occurrence_threshold (défaut 3,
   paramètre injectable du use case) :
     → CategorizationSuggestion(compte_code=pattern.compte_code, confidence=élevée,
                                  source=PATTERN)
4. SINON :
     → candidates = AccountRetriever.search(libelle + tiers, top_k=5)
     → prendre le meilleur candidat ; confidence dérivée du score de retrieval
5. SI confidence >= seuil_validation (défaut 0.85, configurable) :
     → statut = AUTO_VALIDATED
   SINON :
     → statut = PENDING_REVIEW  (file d'attente Human Review)
6. Persister CategorizationDecision via CategorizationDecisionRepository
```

### `ValidateCategorization` use case (Human Review)

```
1. Le comptable confirme ou corrige compte_code pour une décision PENDING_REVIEW
2. statut → HUMAN_VALIDATED, validated_by = user_id
3. Upsert CategorizationPattern (tenant_id, libelle_pattern, fournisseur, compte_code)
   — SEULE une validation humaine met à jour la table de patterns.
   Les auto-validations n'alimentent pas l'apprentissage, pour éviter qu'une erreur
   automatique ne se renforce elle-même sans supervision.
```

Ce choix diverge délibérément de `reconciliation_patterns.py` (qui apprend de tout match
accepté) : une erreur de rapprochement bancaire est réversible et sans impact fiscal direct ;
une erreur de catégorisation PCG peut fausser un bilan. La contrainte #3 d'ARCHITECTURE.md
("human-in-the-loop non négociable") justifie ce garde-fou supplémentaire.

---

## Gestion des cas d'erreur

- **Aucun candidat retourné par le RAG** (corpus vide, requête dégénérée) :
  `CategorizationSuggestion` vide → statut `PENDING_REVIEW`, confidence 0.0, pas d'exception —
  cohérent avec le principe déjà établi (`MissingTenantContextError` du module tenancy) de ne
  jamais faire échouer silencieusement une requête scoping-sensible.
- **Contexte tenant manquant** : `MissingTenantContextError` (domain/tenancy) existe dans le code
  mais n'est actuellement levée nulle part — le comportement réel du reste du projet est que RLS
  retourne silencieusement zéro ligne quand le contexte n'est pas posé. Cette brique suit le même
  comportement réel (pas d'exception ajoutée) plutôt que la levée aspirationnelle initialement
  prévue ici, pour rester cohérente avec `tenancy` et `rapprochement`.
- **Candidats RAG à score très proche (ambiguïté)** : réduire la confidence proportionnellement
  à l'écart entre le 1er et le 2e candidat plutôt que de trancher arbitrairement — un score
  serré doit statistiquement plus souvent finir en Human Review.

---

## Stratégie de test

### Niveau 1 — Domain
`tests/domain/categorization/` — entités et value objects, sans dépendance.

### Niveau 2 — Application (fakes mémoire)
`tests/application/categorization/` — `CategorizeEcriture` et `ValidateCategorization` testés
avec un `InMemoryCategorizationPatternRepository` et un `AccountRetriever` stub (retours
scriptés). Couvre notamment : pattern trouvé avec occurrence suffisante vs insuffisante,
seuil de confiance franchi vs non franchi, non-apprentissage sur auto-validation.

### Niveau 3 — Infrastructure (Postgres réel, `integration`)
`tests/infrastructure/db/categorization/` — persistance des patterns et décisions, RLS
(mêmes garanties d'isolation multi-tenant que `tenancy`).

### Niveau 4 — Évaluation (hors suite pytest, local uniquement)
Un script d'évaluation (`scripts/eval_categorization.py`, jamais alimenté avec des données
committées) rejoue les deux exercices FEC du tenant pilote : pour chaque écriture passée, on
fait tourner `CategorizeEcriture` sur le libellé réel, et on compare la prédiction au `CompteNum`
réel (normalisé sur les 6 premiers caractères — voir note de format ci-dessus en Contexte).
Le format FEC standardisé rend cette comparaison **exacte** (précision top-1 réelle), pas un
proxy heuristique. Métriques : précision top-1, taux d'escalade Human Review, répartition
PATTERN vs RAG. Ce harness ne fait pas partie de la CI — il sert à calibrer les seuils
(`min_occurrence_threshold`, `seuil_validation`) avant la mise en production sur un tenant réel.

---

## Lacunes connues (à adresser dans des briques suivantes)

- **Normalisation du libellé** : la logique de normalisation utilisée par `rapprochement`
  pourrait converger avec celle de `categorization` — à factoriser si la duplication devient
  gênante, pas avant.
- **Gouvernance du référentiel PCG** : mise à jour du corpus (nouveaux comptes, PCG révisé)
  non traitée.
- **Multi-compte par écriture** : une facture avec plusieurs lignes de nature différente
  (ex. abonnement + frais de port) nécessiterait une catégorisation par ligne, pas juste par
  écriture globale — non couvert par cette première itération.

---

## ADR associé

Cette brique matérialise **ADR-002** (`ARCHITECTURE.md`) — RAG Hybride sur le Plan Comptable
Général. Elle introduit un raffinement non prévu dans l'ADR initial : la couche
`CategorizationPattern` par tenant, qui court-circuite le RAG pour les fournisseurs déjà connus
et réduit le coût/latence par rapport à un appel RAG systématique.
