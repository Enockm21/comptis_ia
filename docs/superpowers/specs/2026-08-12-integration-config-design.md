# Interface d'administration Comptis — Intégrations & Canvas IA

## Objectif

Fournir aux administrateurs d'organisation une interface web (React + TypeScript) pour :
1. Configurer les intégrations externes (nom libre, URL API, URL MCP, token chiffré).
2. Visualiser les intégrations, les flux de données et les décisions IA via un canvas ReactFlow.
3. Suivre les décisions IA en temps réel lors du lancement d'un rapprochement depuis l'UI.

---

## Architecture globale

**Monorepo** — un seul dépôt, deux dossiers racine :

```
comptis/
├── src/comptis/        # Backend FastAPI (Python, Clean Architecture)
└── frontend/           # App React + TypeScript (Vite)
```

**En développement :** deux serveurs — FastAPI sur `:8000`, Vite sur `:5173` (proxy `/api` → `:8000`).

**En production :** `vite build` génère `frontend/dist/`. FastAPI sert les fichiers statiques via `StaticFiles` à la racine `/`. L'API reste sous `/api` et `/admin`.

---

## Sous-projet 1 — Config des intégrations

### 1.1 Base de données

Nouvelle table `org_integrations` :

| Colonne | Type | Contraintes |
|---|---|---|
| `id` | UUID | PK |
| `organization_id` | UUID | FK → `organizations`, NOT NULL |
| `name` | VARCHAR(100) | NOT NULL |
| `api_url` | VARCHAR(500) | nullable |
| `mcp_url` | VARCHAR(500) | nullable |
| `token_encrypted` | BYTEA | nullable — Fernet AES-128 |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Contrainte : `UNIQUE(organization_id, name)`.

**Chiffrement du token :** clé Fernet lue depuis `COMPTIS_ENCRYPTION_KEY` (env var, base64 32 bytes). C'est le seul secret qui reste dans `.env` — ce n'est pas un secret métier, c'est une clé de chiffrement.

### 1.2 Couches backend (Clean Architecture)

**Domain** — `src/comptis/domain/integrations/entities.py`
- `Integration` : dataclass avec `id`, `organization_id`, `name`, `api_url`, `mcp_url`, `token_set: bool` (le token brut n'est jamais exposé hors infra).

**Application** — `src/comptis/application/integrations/use_cases.py`
- `ListIntegrations(org_id)` → `list[Integration]`
- `GetIntegration(org_id, name)` → `Integration`
- `UpsertIntegration(org_id, name, api_url, mcp_url, token?)` → `Integration`
- `DeleteIntegration(org_id, name)` → None

**Infrastructure** — `src/comptis/infrastructure/db/integration_repository.py`
- `SQLAlchemyIntegrationRepository` : chiffre/déchiffre le token avec Fernet.
- `FernetTokenCipher` : wraps `cryptography.fernet.Fernet`.

**Interface** — `src/comptis/interface/api/admin/integrations/router.py`

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/admin/integrations` | Liste les intégrations de l'org |
| `GET` | `/admin/integrations/{name}` | Détail d'une intégration |
| `PUT` | `/admin/integrations/{name}` | Crée ou met à jour |
| `DELETE` | `/admin/integrations/{name}` | Supprime |

Auth : dépendance `require_admin` — JWT valide + `role="admin"` dans `memberships` pour l'organisation courante. Sinon → 403.

**Réponse GET (token jamais en clair) :**
```json
{
  "name": "pnicompta",
  "api_url": "https://host/api",
  "mcp_url": "https://host/mcp",
  "token_set": true,
  "updated_at": "2026-08-12T10:00:00Z"
}
```

**Body PUT :**
```json
{
  "api_url": "https://host/api",
  "mcp_url": "https://host/mcp",
  "token": "cpt_..."
}
```
Si `token` est absent du body → le token existant est conservé.

### 1.3 Migration du routeur de rapprochement

`_build_mcp_client()` dans `router.py` devient async. Priorité :
1. Cherche l'intégration `"pnicompta"` en DB pour l'org courante.
2. Fallback → env vars `PNICOMPTA_API_URL` / `PNICOMPTA_MCP_URL` / `PNICOMPTA_API_TOKEN`.

Rien ne casse si la DB est vide.

### 1.4 Frontend — Page config

Route React : `/admin/integrations`

**Comportement :**
- Chargement : `GET /admin/integrations` → liste les intégrations existantes.
- Chaque intégration affichée dans une carte : nom, API URL, MCP URL, token masqué (booléen), bouton Éditer, bouton Supprimer.
- Bouton "+ Nouvelle intégration" ouvre un formulaire inline.
- Formulaire : `name` (texte libre), `api_url`, `mcp_url` (optionnel), `token` (input password avec toggle visibilité).
- Sauvegarde : `PUT /admin/integrations/{name}`. Si le champ token est vide → ne pas l'envoyer dans le body.
- Suppression : `DELETE /admin/integrations/{name}` avec confirmation.
- Messages succès/erreur inline (pas de modales).

**Auth frontend :** JWT stocké en `localStorage`. Toutes les requêtes `fetch()` ajoutent `Authorization: Bearer {token}`.

---

## Sous-projet 2 — Canvas ReactFlow (historique)

Route React : `/admin/canvas`

### Nœuds

| Type de nœud | Description |
|---|---|
| `ComptisNode` | Nœud central — Comptis |
| `IntegrationNode` | Une intégration externe (PNiCompta, etc.) |
| `RunNode` | Un run de rapprochement (date, statut) |
| `DecisionNode` | Une décision IA (match, conflict, skip) |

### Edges

- `IntegrationNode → ComptisNode` : connexion active (libellé : flux données)
- `ComptisNode → RunNode` : run lancé
- `RunNode → DecisionNode` : décision prise durant ce run

### Données

Nouvel endpoint : `GET /admin/runs` → liste des runs avec décisions.

```json
[
  {
    "run_id": "uuid",
    "started_at": "...",
    "status": "completed",
    "decisions": [
      {
        "type": "match",
        "invoice_id": 1,
        "transaction_id": 42,
        "confidence": 0.97,
        "reason": "montant identique, même fournisseur"
      }
    ]
  }
]
```

Le canvas construit le graphe ReactFlow depuis ces données. Layout automatique (Dagre ou ELK).

---

## Sous-projet 3 — Temps réel

Route : bouton "Lancer rapprochement" depuis le canvas.

**Flux :**
1. `POST /admin/runs/start` → démarre un run, retourne `run_id`.
2. `GET /admin/runs/{run_id}/stream` → SSE (Server-Sent Events), envoie les décisions au fil de l'eau.
3. Le frontend s'abonne au SSE et ajoute des `DecisionNode` au canvas en temps réel.
4. Quand le stream se ferme → run terminé, canvas figé.

**Format SSE :**
```
event: decision
data: {"type":"match","invoice_id":1,"transaction_id":42,"confidence":0.97}

event: done
data: {}
```

---

## Stack technique

| Couche | Techno |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, Alembic, `cryptography` (Fernet) |
| Frontend | React 18, TypeScript, Vite, ReactFlow, React Router v6 |
| Auth | JWT (existant) + rôle `admin` sur `memberships` |
| Dev | Vite proxy `/api` → FastAPI `:8000` |
| Prod | `vite build` → `frontend/dist/` servi par FastAPI `StaticFiles` |

---

## Séquence d'implémentation

1. **SP1-Backend** : migration Alembic, modèle SQLAlchemy, repo Fernet, use cases, router admin, `require_admin`.
2. **SP1-Frontend** : scaffold Vite + React + TypeScript, React Router, page `/admin/integrations`.
3. **SP2** : endpoint `GET /admin/runs`, canvas ReactFlow, nœuds et layout.
4. **SP3** : endpoint SSE `GET /admin/runs/{id}/stream`, intégration live canvas.
