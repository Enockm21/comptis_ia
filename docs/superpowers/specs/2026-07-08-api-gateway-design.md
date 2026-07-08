# API Gateway — Design Spec

**Date :** 2026-07-08
**Auteur :** Enock Maya
**Brique :** 2 / 7 (après multi-tenant foundations)

---

## Contexte

Les fondations multi-tenant (Organisation / Tenant / User / Membership + RLS Postgres) sont en place. Cette brique ajoute le point d'entrée HTTP de l'application : authentification email+password avec JWT, validation des API keys machine, et injection du contexte RLS sur chaque requête authentifiée.

---

## Périmètre

**Inclus :**
- `POST /auth/register` — création de compte utilisateur
- `POST /auth/login` — obtention access_token + refresh_token
- `POST /auth/refresh` — renouvellement de l'access_token
- Dépendance `require_user()` — protège les routes utilisateur (JWT Bearer)
- Dépendance `require_api_key()` — protège les routes machine (X-API-Key)
- Deux nouvelles migrations DB : `password_hash` sur `users`, table `api_keys`

**Hors périmètre :**
- Endpoint de création/révocation d'API key (brique Organisation)
- Logout / blacklist de tokens
- Rate limiting
- CORS
- OAuth2 / SSO

---

## Architecture

### Couches (Clean Architecture)

```
interface/
  api/
    auth/
      router.py       → routes FastAPI : register, login, refresh
      schemas.py      → Pydantic : RegisterRequest, LoginRequest, TokenResponse…
    dependencies.py   → require_user(), require_api_key(), get_db_session()
    main.py           → création app FastAPI, montage routers

application/
  auth/
    use_cases.py      → RegisterUser, LoginUser, RefreshToken (dataclasses)
    ports.py          → Protocol : PasswordHasher, TokenService, UserRepository (réutilise port existant)

infrastructure/
  auth/
    jwt.py            → encode/decode JWT (PyJWT)
    password.py       → bcrypt hash/verify
    api_key.py        → lookup API key hashée en DB
  db/
    migrations/
      versions/
        0002_add_auth.py  → password_hash sur users + table api_keys
```

### Règle de dépendance

```
interface → application → domain
interface → infrastructure
application → domain
```

`application/auth/` ne connaît ni FastAPI ni SQLAlchemy — uniquement les Protocols définis dans ses ports.

---

## Schéma DB (migration 0002)

**Modification table `users` :**
```sql
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT '';
```

**Nouvelle table `api_keys` :**
```sql
CREATE TABLE api_keys (
    id           UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    key_hash     VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256 hex
    created_at   TIMESTAMPTZ NOT NULL
);
GRANT SELECT ON api_keys TO comptis_app;
```

La clé brute n'est jamais stockée — seulement son SHA-256. Elle est affichée en clair une seule fois à la création (hors périmètre de cette brique).

---

## Flux d'authentification

### Register — `POST /auth/register`

```
{ email, password }
→ RegisterUser use case
  → UserRepository.get_by_email → 409 si email pris
  → PasswordHasher.hash(password)
  → UserRepository.save(User) avec password_hash
← { user_id, email }
```

### Login — `POST /auth/login`

```
{ email, password }
→ LoginUser use case
  → UserRepository.get_by_email → 401 si absent
  → PasswordHasher.verify(password, hash) → 401 si invalide
  → TokenService.create_access_token(user_id)   # exp: 15 min
  → TokenService.create_refresh_token(user_id)  # exp: 7 jours
← { access_token, refresh_token, token_type: "bearer" }
```

### Refresh — `POST /auth/refresh`

```
{ refresh_token }
→ RefreshToken use case
  → TokenService.decode(token) → vérifie type=="refresh" et exp
  → TokenService.create_access_token(user_id)
← { access_token, token_type: "bearer" }
```

### Payload JWT

```json
{ "sub": "<user_id>", "type": "access|refresh", "exp": <unix_timestamp> }
```

### Requête protégée — utilisateur

```
Authorization: Bearer <access_token>
→ Depends(require_user)
  → TokenService.decode → user_id
  → ouvre AsyncSession (app_engine, RLS enforced)
  → set_tenant_context(session, user_id=user_id)
  → yield CurrentUser(id=user_id)
```

### Requête protégée — API key machine

```
X-API-Key: <clé brute>
→ Depends(require_api_key)
  → SHA-256(clé reçue) → lookup api_keys.key_hash
  → 401 si absent
  → ouvre AsyncSession
  → set_tenant_context(session, organization_id=org_id)
  → yield CurrentOrg(id=org_id)
```

---

## Gestion des erreurs

Format uniforme pour toutes les erreurs auth :

```json
{ "detail": { "code": "<slug>", "message": "<human readable>" } }
```

| Situation | HTTP | code |
|-----------|------|------|
| Email déjà utilisé | 409 | `email_already_registered` |
| Email/password invalide | 401 | `invalid_credentials` |
| Token expiré | 401 | `token_expired` |
| Token invalide | 401 | `invalid_token` |
| API key inconnue | 401 | `invalid_api_key` |
| Route protégée sans auth | 401 | `not_authenticated` |

Les erreurs 401 ne distinguent jamais "email inconnu" de "mauvais mot de passe" — empêche l'énumération d'emails.

---

## Tests

### Unitaires (sans DB, sans FastAPI)

- `RegisterUser` avec `FakeUserRepository` + `FakePasswordHasher`
  - cas nominal, cas email doublon
- `LoginUser` avec fakes
  - cas nominal, email inconnu, mauvais password
- `RefreshToken` avec fake `TokenService`
  - cas nominal, token expiré, mauvais type

### Intégration (testcontainers + httpx.AsyncClient)

- `POST /auth/register` → 201
- `POST /auth/register` (doublon) → 409
- `POST /auth/login` (ok) → 200 + tokens
- `POST /auth/login` (mauvais password) → 401
- `POST /auth/refresh` → 200 + nouveau access_token
- Route protégée avec token valide → 200
- Route protégée sans token → 401
- Route protégée avec API key valide → 200

---

## Stack technique

**Packages à ajouter :**

```toml
fastapi>=0.115
uvicorn[standard]>=0.30
httpx>=0.27
pyjwt[crypto]>=2.8
bcrypt>=4.1
```

**Variables d'environnement :**

```env
JWT_SECRET_KEY=<min 32 chars>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Point d'entrée :**

```bash
uvicorn src.comptis.interface.api.main:app --reload
```

---

## Ce qui vient après

Cette brique débloque la brique suivante : **Ingestion pipeline** (les endpoints d'upload de factures seront protégés par `require_api_key` ou `require_user`).

La gestion des API keys (création, révocation, listing) viendra avec la brique **Organisation** qui expose les endpoints CRUD de gestion de compte.
