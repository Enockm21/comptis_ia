# UI de revue des conflits de rapprochement — Spec de conception

**Date :** 2026-08-12
**Auteur :** Enock Maya
**Brique :** SP2 — Interface de revue humaine du rapprochement
**Statut :** Approuvé pour implémentation

---

## Contexte

Le backend du rapprochement existe déjà (`domain/rapprochement`, `application/rapprochement`,
`infrastructure/agents/rapprochement` — agent LangGraph fetch/match/human_review/report,
scorer flou, arbitre LLM) et expose un router `/reconciliation` (`POST /run`,
`GET /run/{id}/conflicts`, `POST /run/{id}/resolve`, `GET /run/{id}/report`). Il n'existe
aucune interface pour l'utiliser : aujourd'hui, déclencher un rapprochement et trancher les
conflits n'est possible qu'en appelant l'API directement.

Cette brique ajoute l'interface web permettant à un comptable de déclencher un rapprochement,
réviser les conflits en attente et consulter le rapport final — plus les correctifs backend
nécessaires pour que ce flux soit utilisable et sûr par un utilisateur humain authentifié.

---

## Périmètre

### Inclus
- Page de connexion (email/mot de passe, JWT) — inexistante aujourd'hui.
- Migration du router `/reconciliation` de `require_api_key` (clé API org, pensée pour un
  accès machine) vers `require_user` (JWT comptable) sur `POST /run` et `POST /resolve`.
- Ajout d'authentification sur `GET .../conflicts` et `GET .../report` (aucune aujourd'hui —
  faille de sécurité : n'importe qui connaissant un `run_id` peut lire les données d'un tenant).
- Exposition de la facture candidate dans `ConflictSchema` (le domaine la porte déjà via
  `Conflict.facture`, l'API ne la renvoie pas).
- Nouvel endpoint `GET /tenants` — liste des tenants visibles par l'utilisateur connecté.
- Page frontend `/reconciliation` : déclenchement → révision des conflits (un par un) → rapport.

### Explicitement hors périmètre
- **Historique des runs** — le stockage reste en mémoire côté backend (`_runs: dict`,
  déjà marqué MVP dans le code). Pas de liste des runs passés, pas de persistance Postgres.
  Un rechargement de page ou un redémarrage serveur perd le run en cours.
- **Matching manuel** des transactions non rapprochées (`unmatched`) — affichage seul.
- **Tests automatisés frontend** — aucune infra de test JS dans le repo aujourd'hui
  (cohérent avec la page `AdminIntegrations` existante, vérifiée manuellement).
- **Rôles différenciés** (accountant vs viewer) — `require_user` suffit ; pas de contrôle
  de rôle fin sur ce flux pour cette V1.

---

## Bloc 1 — Auth & correctifs backend

### 1.1 Router `/reconciliation` — changement d'authentification

| Endpoint | Avant | Après |
|---|---|---|
| `POST /run` | `require_api_key` (org_id) | `require_user` (user_id) |
| `POST /run/{id}/resolve` | `require_api_key` | `require_user` |
| `GET /run/{id}/conflicts` | aucune | `require_user` |
| `GET /run/{id}/report` | aucune | `require_user` |

`_build_mcp_client_for_org(org_id, session)` a besoin d'un `org_id`, qui ne vient plus de la
dépendance d'auth. Il est dérivé du `tenant_id` fourni dans `RunRequest` :
`TenantRepository.get_by_id(tenant_id).organization_id`. La RLS sur `tenants` autorise cette
lecture sous contexte `require_user` via la policy `membership_access` existante (le
`tenant_id` choisi appartient forcément à un tenant où l'utilisateur a une membership, sinon
`GET /tenants` ne l'aurait pas listé).

Sur `GET .../conflicts` et `GET .../report`, en plus de `require_user`, vérifier que
`run["tenant_id"]` correspond à un tenant accessible par l'utilisateur courant (même requête
`get_by_id` + comparaison — si `None`, 404 plutôt que 403 pour ne pas révéler l'existence du run).

### 1.2 `ConflictSchema` — exposer la facture candidate

```python
class FactureSchema(BaseModel):
    id: str
    montant: Decimal
    date: date
    fournisseur: str

class ConflictSchema(BaseModel):
    transaction: TransactionSchema
    facture: FactureSchema | None
    raison: str
    composite_score: float
```

`get_conflicts` construit `ConflictSchema.facture` depuis `Conflict.facture` (déjà présent côté
domaine, jamais sérialisé jusqu'ici).

### 1.3 `GET /tenants` — nouveau endpoint

Router : `src/comptis/interface/api/tenancy/router.py` (nouveau, layer `interface`).

```python
@router.get("/tenants", response_model=list[TenantSchema])
async def list_my_tenants(
    user_id: UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TenantSchema]:
    repo = SQLAlchemyTenantRepository(session)
    return [TenantSchema(id=t.id, name=t.name) for t in await repo.list_visible(session)]
```

Nouvelle méthode sur `TenantRepository` (port + impl SQLAlchemy) :

```python
async def list_visible(self, session: AsyncSession) -> list[Tenant]:
    # Pas de clause WHERE — la RLS filtre via membership_access sous contexte require_user
    result = await session.execute(select(TenantModel))
    return [_tenant_to_domain(m) for m in result.scalars().all()]
```

Fonctionne car `require_user` pose uniquement `app.current_user_id` (pas
`app.current_organization_id`), donc seule la policy `membership_access` matche — exactement
la sémantique voulue : "les tenants où j'ai une ligne de membership".

---

## Bloc 2 — Frontend

### 2.1 Page de connexion (`/login`, nouvelle)

Formulaire email + mot de passe → `POST /auth/login` → stocke `access_token` (réutilise
`lib/auth.ts::setToken`) → redirige vers `/reconciliation`. Erreur affichée inline si 401.

Garde de route minimal dans `App.tsx` : si `getToken()` est `null` et la route n'est pas
`/login`, redirection vers `/login`.

### 2.2 Page Rapprochement (`/reconciliation`, nouvelle, devient la route par défaut)

Un flux séquentiel en trois étapes dans une seule page (état local React, pas de routes
séparées par étape — pas de persistance de run à reprendre, donc pas de valeur à des URLs
dédiées par étape).

**Étape 1 — Déclenchement**
- Sélecteur de tenant peuplé par `GET /tenants` (chargé au montage de la page).
- Deux champs date optionnels (`date_debut`, `date_fin`).
- Bouton "Lancer le rapprochement" → `POST /run`, état de chargement pendant l'appel
  (peut prendre plusieurs secondes : fetch transactions/factures + scoring + arbitre LLM sur
  les cas gris).
- À la réception de `RunResponse` : passe automatiquement à l'étape 2 (`GET .../conflicts`).

**Étape 2 — Révision des conflits (un par un)**
- Si la liste des conflits est vide → passe directement à l'étape 3.
- Sinon, affiche le premier conflit : transaction et facture candidate côte à côte
  (montant, date, libellé/fournisseur), `raison` (`confidence_insuffisante` |
  `ecart_montant`) et `composite_score`. Compteur "Conflit X / N" en haut.
- Trois boutons : **Confirmer** (`decision: "confirmer"`) / **Écart accepté**
  (`"ecart_accepte"`) / **Rejeter** (`"rejeter"`) → `POST /resolve`.
- Après chaque décision : refetch `GET .../conflicts`. Si la liste est vide → étape 3,
  sinon affiche le conflit suivant.

**Étape 3 — Rapport**
- `GET .../report` → affiche les totaux (transactions, rapprochées, non rapprochées, écarts)
  et deux tableaux : matches (facture/transaction/statut/écart) et transactions non
  rapprochées.
- Bouton "Nouveau rapprochement" → retour à l'étape 1 (réinitialise l'état local).

### 2.3 Fichiers frontend

```
frontend/src/
├── pages/
│   ├── Login.tsx                  (nouveau)
│   └── Reconciliation.tsx         (nouveau)
├── components/
│   ├── ConflictReview.tsx         (nouveau — étape 2)
│   └── ReconciliationReport.tsx   (nouveau — étape 3)
└── lib/
    ├── auth.ts                    (modifié — ajout login())
    └── api.ts                     (modifié — namespace reconciliation + tenants)
```

`App.tsx` : ajoute les routes `/login` et `/reconciliation` ; `/reconciliation` devient la
route par défaut (remplace `/admin/integrations`, qui reste accessible mais n'est plus la
racine).

---

## Bloc 3 — Stratégie de test

Backend (suit le pattern TDD déjà en place : domain → application fakes → infra/interface
avec testcontainers) :
- `ConflictSchema` sérialise correctement une facture optionnelle (présente / absente).
- `TenantRepository.list_visible()` — un utilisateur avec membership sur le tenant A voit A
  mais pas B (test d'isolation RLS, même approche que `test_isolation.py`).
- Intégration (`httpx.AsyncClient`) : `GET /tenants` retourne les tenants du user connecté ;
  `GET .../conflicts` et `.../report` renvoient 401 sans token, 404 si le tenant du run n'est
  pas accessible à l'utilisateur ; flux complet run → resolve → report reste vert avec
  `require_user`.

Frontend : vérification manuelle dans le navigateur — login → sélection tenant → lancement
d'un run → révision d'un conflit (les trois décisions) → rapport final. Pas de tests
automatisés (cohérent avec le reste du frontend).

---

## Stack technique

| Couche | Techno |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy async (RLS existante réutilisée) |
| Frontend | React 18, TypeScript, Vite, React Router v6 (existant, pas de nouvelle dépendance) |
| Auth | JWT existant (`require_user`), pas de nouveau mécanisme |

---

## Séquence d'implémentation

1. **Backend** : `FactureSchema` + `ConflictSchema.facture`, `TenantRepository.list_visible`,
   router `/tenants`, migration `require_api_key` → `require_user` sur `/reconciliation`
   (+ vérification d'accès tenant sur `conflicts`/`report`), tests.
2. **Frontend — Login** : page `/login`, garde de route.
3. **Frontend — Rapprochement** : page `/reconciliation` avec les trois étapes, composants
   `ConflictReview` et `ReconciliationReport`, client API.
4. **Vérification manuelle** en navigateur du flux complet.
