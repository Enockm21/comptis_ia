# API Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add FastAPI auth layer (register/login/refresh + JWT + API key validation) on top of the existing multi-tenant foundations.

**Architecture:** Dependency-injection per route (FastAPI `Depends`). No global middleware. `require_user()` decodes JWT and calls `set_tenant_context(user_id=...)`. `require_api_key()` hashes the incoming key, looks it up in `api_keys` table, calls `set_tenant_context(organization_id=...)`. Auth use cases live in `application/auth/`, implementations in `infrastructure/auth/`, routes in `interface/api/`.

**Tech Stack:** FastAPI 0.115+, PyJWT 2.8+ (HS256), bcrypt 4.1+, httpx 0.27+ (test client), email-validator 2.0+, existing SQLAlchemy async + testcontainers stack.

## Global Constraints

- Python ≥ 3.12, SQLAlchemy 2.0 async, Alembic migrations
- Clean Architecture: domain ← application ← infrastructure ← interface. No layer imports from an outer layer.
- All async DB calls use `AsyncSession` from `app_engine` (comptis_app role, RLS enforced)
- Migrations use psycopg (sync) driver; app uses asyncpg
- `pytestmark = pytest.mark.asyncio(loop_scope="session")` on every test module using session-scoped fixtures
- Commit message format: `type(scope): description`
- Ruff line-length = 100

---

## File Map

**New files:**
```
src/comptis/application/auth/__init__.py
src/comptis/application/auth/exceptions.py
src/comptis/application/auth/ports.py
src/comptis/application/auth/use_cases.py

src/comptis/infrastructure/auth/__init__.py
src/comptis/infrastructure/auth/password.py
src/comptis/infrastructure/auth/jwt.py
src/comptis/infrastructure/auth/api_key.py

src/comptis/infrastructure/db/migrations/versions/0002_add_auth.py

src/comptis/interface/api/__init__.py
src/comptis/interface/api/auth/__init__.py
src/comptis/interface/api/auth/schemas.py
src/comptis/interface/api/auth/router.py
src/comptis/interface/api/dependencies.py
src/comptis/interface/api/main.py

tests/application/auth/__init__.py
tests/application/auth/test_use_cases.py

tests/infrastructure/auth/__init__.py
tests/infrastructure/auth/test_password.py
tests/infrastructure/auth/test_jwt.py

tests/interface/__init__.py
tests/interface/api/__init__.py
tests/interface/api/conftest.py
tests/interface/api/test_auth.py
```

**Modified files:**
```
pyproject.toml                                    → add fastapi, uvicorn, httpx, pyjwt, bcrypt, email-validator
src/comptis/infrastructure/db/models.py           → add password_hash to UserModel, add ApiKeyModel
src/comptis/infrastructure/db/repositories.py     → extend SQLAlchemyUserRepository, add SQLAlchemyApiKeyRepository
```

---

## Task 1: Dependencies + Migration + ORM Models

**Files:**
- Modify: `pyproject.toml`
- Create: `src/comptis/infrastructure/db/migrations/versions/0002_add_auth.py`
- Modify: `src/comptis/infrastructure/db/models.py`

**Interfaces:**
- Produces: `UserModel.password_hash` (str), `ApiKeyModel` (id, organization_id, name, key_hash, created_at)

- [ ] **Step 1: Add dependencies to pyproject.toml**

Replace the `[project]` dependencies block:

```toml
[project]
name = "comptis"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.29",
    "psycopg[binary]>=3.1",
    "pydantic>=2.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pyjwt[crypto]>=2.8",
    "bcrypt>=4.1",
    "email-validator>=2.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "testcontainers[postgres]>=4.0",
    "httpx>=0.27",
    "ruff>=0.4",
]
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync
```

Expected: packages installed, no errors.

- [ ] **Step 3: Write migration 0002**

Create `src/comptis/infrastructure/db/migrations/versions/0002_add_auth.py`:

```python
"""Add password_hash to users and create api_keys table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(255), nullable=False, server_default=""),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON api_keys TO comptis_app")


def downgrade() -> None:
    op.execute("REVOKE ALL PRIVILEGES ON api_keys FROM comptis_app")
    op.drop_table("api_keys")
    op.drop_column("users", "password_hash")
```

- [ ] **Step 4: Update ORM models**

In `src/comptis/infrastructure/db/models.py`, replace `UserModel` and add `ApiKeyModel` at the end:

```python
class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(sa.String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255), nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )


class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True, default=_uuid)
    organization_id: Mapped[UUID] = mapped_column(
        sa.Uuid, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )
```

- [ ] **Step 5: Verify existing tests still pass (non-integration)**

```bash
uv run pytest -v -m "not integration"
```

Expected: 18 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock \
  src/comptis/infrastructure/db/models.py \
  src/comptis/infrastructure/db/migrations/versions/0002_add_auth.py
git commit -m "feat(infra): add auth dependencies, migration 0002, and ORM updates"
```

---

## Task 2: Application Auth Layer (TDD)

**Files:**
- Create: `src/comptis/application/auth/__init__.py`
- Create: `src/comptis/application/auth/exceptions.py`
- Create: `src/comptis/application/auth/ports.py`
- Create: `src/comptis/application/auth/use_cases.py`
- Create: `tests/application/auth/__init__.py`
- Create: `tests/application/auth/test_use_cases.py`

**Interfaces:**
- Consumes: `User` from `comptis.domain.tenancy.entities`, `UUID` from stdlib
- Produces:
  - `EmailAlreadyRegisteredError`, `InvalidCredentialsError`, `TokenExpiredError`, `InvalidTokenError`
  - `PasswordHasher` Protocol: `hash(password: str) -> str`, `verify(password: str, hashed: str) -> bool`
  - `TokenService` Protocol: `create_access_token(user_id: UUID) -> str`, `create_refresh_token(user_id: UUID) -> str`, `decode(token: str) -> dict` (raises `TokenExpiredError` | `InvalidTokenError`)
  - `AuthUserRepository` Protocol: `get_by_email(email: str) -> User | None`, `save_with_credentials(user: User, password_hash: str) -> None`, `get_password_hash(user_id: UUID) -> str | None`
  - `RegisterUser.execute(email, password) -> User`
  - `LoginUser.execute(email, password) -> tuple[str, str]`
  - `RefreshToken.execute(refresh_token: str) -> str`

- [ ] **Step 1: Create `__init__.py` files**

```bash
touch src/comptis/application/auth/__init__.py
touch tests/application/auth/__init__.py
```

- [ ] **Step 2: Write exceptions**

Create `src/comptis/application/auth/exceptions.py`:

```python
class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


class InvalidTokenError(Exception):
    pass
```

- [ ] **Step 3: Write ports**

Create `src/comptis/application/auth/ports.py`:

```python
from typing import Protocol
from uuid import UUID

from comptis.domain.tenancy.entities import User


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hashed: str) -> bool: ...


class TokenService(Protocol):
    def create_access_token(self, user_id: UUID) -> str: ...
    def create_refresh_token(self, user_id: UUID) -> str: ...
    def decode(self, token: str) -> dict: ...


class AuthUserRepository(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...
    async def save_with_credentials(self, user: User, password_hash: str) -> None: ...
    async def get_password_hash(self, user_id: UUID) -> str | None: ...
```

- [ ] **Step 4: Write the failing tests**

Create `tests/application/auth/test_use_cases.py`:

```python
from uuid import UUID, uuid4

import pytest

from comptis.application.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
from comptis.application.auth.use_cases import LoginUser, RefreshToken, RegisterUser
from comptis.domain.tenancy.entities import User

pytestmark = pytest.mark.asyncio(loop_scope="session")


# --- Fakes ---

class FakePasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed: str) -> bool:
        return hashed == f"hashed:{password}"


class FakeTokenService:
    def create_access_token(self, user_id: UUID) -> str:
        return f"access:{user_id}"

    def create_refresh_token(self, user_id: UUID) -> str:
        return f"refresh:{user_id}"

    def decode(self, token: str) -> dict:
        if token.startswith("access:"):
            return {"sub": token[7:], "type": "access"}
        if token.startswith("refresh:"):
            return {"sub": token[8:], "type": "refresh"}
        if token == "expired":
            raise TokenExpiredError()
        raise InvalidTokenError()


class FakeAuthUserRepository:
    def __init__(self):
        self._users: dict[str, User] = {}
        self._hashes: dict[UUID, str] = {}

    async def get_by_email(self, email: str) -> User | None:
        return self._users.get(email)

    async def save_with_credentials(self, user: User, password_hash: str) -> None:
        self._users[user.email] = user
        self._hashes[user.id] = password_hash

    async def get_password_hash(self, user_id: UUID) -> str | None:
        return self._hashes.get(user_id)


# --- RegisterUser ---

async def test_register_returns_user():
    repo = FakeAuthUserRepository()
    uc = RegisterUser(user_repo=repo, hasher=FakePasswordHasher())
    user = await uc.execute("alice@test.fr", "secret")
    assert user.email == "alice@test.fr"
    assert isinstance(user.id, UUID)


async def test_register_stores_hashed_password():
    repo = FakeAuthUserRepository()
    uc = RegisterUser(user_repo=repo, hasher=FakePasswordHasher())
    user = await uc.execute("alice@test.fr", "secret")
    stored = await repo.get_password_hash(user.id)
    assert stored == "hashed:secret"


async def test_register_duplicate_email_raises():
    repo = FakeAuthUserRepository()
    uc = RegisterUser(user_repo=repo, hasher=FakePasswordHasher())
    await uc.execute("alice@test.fr", "secret")
    with pytest.raises(EmailAlreadyRegisteredError):
        await uc.execute("alice@test.fr", "other")


# --- LoginUser ---

async def test_login_returns_tokens():
    repo = FakeAuthUserRepository()
    reg = RegisterUser(user_repo=repo, hasher=FakePasswordHasher())
    await reg.execute("bob@test.fr", "pass")
    uc = LoginUser(user_repo=repo, hasher=FakePasswordHasher(), token_service=FakeTokenService())
    access, refresh = await uc.execute("bob@test.fr", "pass")
    assert access.startswith("access:")
    assert refresh.startswith("refresh:")


async def test_login_unknown_email_raises():
    repo = FakeAuthUserRepository()
    uc = LoginUser(user_repo=repo, hasher=FakePasswordHasher(), token_service=FakeTokenService())
    with pytest.raises(InvalidCredentialsError):
        await uc.execute("nobody@test.fr", "pass")


async def test_login_wrong_password_raises():
    repo = FakeAuthUserRepository()
    reg = RegisterUser(user_repo=repo, hasher=FakePasswordHasher())
    await reg.execute("bob@test.fr", "correct")
    uc = LoginUser(user_repo=repo, hasher=FakePasswordHasher(), token_service=FakeTokenService())
    with pytest.raises(InvalidCredentialsError):
        await uc.execute("bob@test.fr", "wrong")


# --- RefreshToken ---

def test_refresh_returns_new_access_token():
    user_id = uuid4()
    svc = FakeTokenService()
    refresh_token = svc.create_refresh_token(user_id)
    uc = RefreshToken(token_service=svc)
    new_access = uc.execute(refresh_token)
    assert new_access.startswith("access:")


def test_refresh_with_expired_token_raises():
    uc = RefreshToken(token_service=FakeTokenService())
    with pytest.raises(TokenExpiredError):
        uc.execute("expired")


def test_refresh_with_invalid_token_raises():
    uc = RefreshToken(token_service=FakeTokenService())
    with pytest.raises(InvalidTokenError):
        uc.execute("garbage")


def test_refresh_with_access_token_raises():
    svc = FakeTokenService()
    access_token = svc.create_access_token(uuid4())
    uc = RefreshToken(token_service=svc)
    with pytest.raises(InvalidTokenError):
        uc.execute(access_token)
```

- [ ] **Step 5: Run tests to see them fail**

```bash
uv run pytest tests/application/auth/test_use_cases.py -v
```

Expected: `ModuleNotFoundError: No module named 'comptis.application.auth.use_cases'`

- [ ] **Step 6: Implement use cases**

Create `src/comptis/application/auth/use_cases.py`:

```python
from dataclasses import dataclass
from uuid import UUID

from comptis.domain.tenancy.entities import User

from .exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
from .ports import AuthUserRepository, PasswordHasher, TokenService


@dataclass
class RegisterUser:
    user_repo: AuthUserRepository
    hasher: PasswordHasher

    async def execute(self, email: str, password: str) -> User:
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise EmailAlreadyRegisteredError(email)
        hashed = self.hasher.hash(password)
        user = User(email=email)
        await self.user_repo.save_with_credentials(user, hashed)
        return user


@dataclass
class LoginUser:
    user_repo: AuthUserRepository
    hasher: PasswordHasher
    token_service: TokenService

    async def execute(self, email: str, password: str) -> tuple[str, str]:
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise InvalidCredentialsError()
        stored_hash = await self.user_repo.get_password_hash(user.id)
        if not stored_hash or not self.hasher.verify(password, stored_hash):
            raise InvalidCredentialsError()
        access_token = self.token_service.create_access_token(user.id)
        refresh_token = self.token_service.create_refresh_token(user.id)
        return access_token, refresh_token


@dataclass
class RefreshToken:
    token_service: TokenService

    def execute(self, refresh_token: str) -> str:
        payload = self.token_service.decode(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenError("not a refresh token")
        user_id = UUID(payload["sub"])
        return self.token_service.create_access_token(user_id)
```

- [ ] **Step 7: Run tests to see them pass**

```bash
uv run pytest tests/application/auth/test_use_cases.py -v
```

Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add src/comptis/application/auth/ tests/application/auth/
git commit -m "feat(application): add auth use cases with unit tests"
```

---

## Task 3: Infrastructure Auth Implementations

**Files:**
- Create: `src/comptis/infrastructure/auth/__init__.py`
- Create: `src/comptis/infrastructure/auth/password.py`
- Create: `src/comptis/infrastructure/auth/jwt.py`
- Create: `src/comptis/infrastructure/auth/api_key.py`
- Modify: `src/comptis/infrastructure/db/repositories.py`
- Create: `tests/infrastructure/auth/__init__.py`
- Create: `tests/infrastructure/auth/test_password.py`
- Create: `tests/infrastructure/auth/test_jwt.py`

**Interfaces:**
- Consumes: `TokenExpiredError`, `InvalidTokenError` from `comptis.application.auth.exceptions`
- Consumes: `ApiKeyModel` from `comptis.infrastructure.db.models`
- Consumes: `UserModel` from `comptis.infrastructure.db.models`
- Produces:
  - `BcryptPasswordHasher` — implements `PasswordHasher` Protocol
  - `JWTTokenService` — implements `TokenService` Protocol (reads `JWT_SECRET_KEY` env var)
  - `get_org_id_for_api_key(session, raw_key) -> UUID | None`
  - `SQLAlchemyUserRepository.save_with_credentials(user, password_hash)` — new method
  - `SQLAlchemyUserRepository.get_password_hash(user_id) -> str | None` — new method

- [ ] **Step 1: Create `__init__.py` files**

```bash
touch src/comptis/infrastructure/auth/__init__.py
touch tests/infrastructure/auth/__init__.py
```

- [ ] **Step 2: Write failing tests for BcryptPasswordHasher**

Create `tests/infrastructure/auth/test_password.py`:

```python
from comptis.infrastructure.auth.password import BcryptPasswordHasher


def test_hash_and_verify_roundtrip():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("my_password")
    assert hasher.verify("my_password", hashed) is True


def test_wrong_password_returns_false():
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash("correct")
    assert hasher.verify("wrong", hashed) is False


def test_two_hashes_of_same_password_differ():
    hasher = BcryptPasswordHasher()
    h1 = hasher.hash("same")
    h2 = hasher.hash("same")
    assert h1 != h2
```

- [ ] **Step 3: Run to see them fail**

```bash
uv run pytest tests/infrastructure/auth/test_password.py -v
```

Expected: `ModuleNotFoundError: No module named 'comptis.infrastructure.auth.password'`

- [ ] **Step 4: Implement BcryptPasswordHasher**

Create `src/comptis/infrastructure/auth/password.py`:

```python
import bcrypt


class BcryptPasswordHasher:
    def hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())
```

- [ ] **Step 5: Run to see them pass**

```bash
uv run pytest tests/infrastructure/auth/test_password.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Write failing tests for JWTTokenService**

Create `tests/infrastructure/auth/test_jwt.py`:

```python
import os
from uuid import uuid4

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-32chars")

from comptis.application.auth.exceptions import InvalidTokenError, TokenExpiredError
from comptis.infrastructure.auth.jwt import JWTTokenService


def test_access_token_roundtrip():
    svc = JWTTokenService()
    user_id = uuid4()
    token = svc.create_access_token(user_id)
    payload = svc.decode(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_refresh_token_roundtrip():
    svc = JWTTokenService()
    user_id = uuid4()
    token = svc.create_refresh_token(user_id)
    payload = svc.decode(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"


def test_invalid_token_raises():
    svc = JWTTokenService()
    with pytest.raises(InvalidTokenError):
        svc.decode("not.a.jwt")


def test_expired_token_raises():
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    svc = JWTTokenService()
    payload = {
        "sub": str(uuid4()),
        "type": "access",
        "exp": datetime.now(tz=timezone.utc) - timedelta(seconds=1),
    }
    expired_token = pyjwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
    with pytest.raises(TokenExpiredError):
        svc.decode(expired_token)
```

- [ ] **Step 7: Run to see them fail**

```bash
uv run pytest tests/infrastructure/auth/test_jwt.py -v
```

Expected: `ModuleNotFoundError: No module named 'comptis.infrastructure.auth.jwt'`

- [ ] **Step 8: Implement JWTTokenService**

Create `src/comptis/infrastructure/auth/jwt.py`:

```python
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt as pyjwt

from comptis.application.auth.exceptions import InvalidTokenError, TokenExpiredError


class JWTTokenService:
    def __init__(self) -> None:
        self._secret = os.environ["JWT_SECRET_KEY"]
        self._algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
        self._access_expire = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
        self._refresh_expire = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    def create_access_token(self, user_id: UUID) -> str:
        return self._encode(str(user_id), "access", timedelta(minutes=self._access_expire))

    def create_refresh_token(self, user_id: UUID) -> str:
        return self._encode(str(user_id), "refresh", timedelta(days=self._refresh_expire))

    def _encode(self, sub: str, type_: str, delta: timedelta) -> str:
        payload = {
            "sub": sub,
            "type": type_,
            "exp": datetime.now(tz=timezone.utc) + delta,
        }
        return pyjwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict:
        try:
            return pyjwt.decode(token, self._secret, algorithms=[self._algorithm])
        except pyjwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except pyjwt.InvalidTokenError:
            raise InvalidTokenError()
```

- [ ] **Step 9: Run to see them pass**

```bash
uv run pytest tests/infrastructure/auth/test_jwt.py -v
```

Expected: 4 passed.

- [ ] **Step 10: Implement API key lookup**

Create `src/comptis/infrastructure/auth/api_key.py`:

```python
import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.models import ApiKeyModel


async def get_org_id_for_api_key(session: AsyncSession, raw_key: str) -> UUID | None:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await session.execute(
        select(ApiKeyModel.organization_id).where(ApiKeyModel.key_hash == key_hash)
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 11: Extend SQLAlchemyUserRepository**

In `src/comptis/infrastructure/db/repositories.py`, add two methods to `SQLAlchemyUserRepository` after the existing `get_by_email` method:

```python
    async def save_with_credentials(self, user: User, password_hash: str) -> None:
        model = UserModel(
            id=user.id, email=user.email,
            password_hash=password_hash, created_at=user.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_password_hash(self, user_id: UUID) -> str | None:
        result = await self._session.execute(
            select(UserModel.password_hash).where(UserModel.id == user_id)
        )
        return result.scalar_one_or_none()
```

Also add `SQLAlchemyApiKeyRepository` at the end of the file:

```python
class SQLAlchemyApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, api_key_id: UUID, organization_id: UUID, name: str, key_hash: str) -> None:
        from datetime import datetime, timezone
        model = ApiKeyModel(
            id=api_key_id,
            organization_id=organization_id,
            name=name,
            key_hash=key_hash,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(model)
        await self._session.flush()
```

Also add `ApiKeyModel` to the import at the top of `repositories.py`:

```python
from .models import ApiKeyModel, MembershipModel, OrganizationModel, TenantModel, UserModel
```

- [ ] **Step 12: Run all unit tests**

```bash
uv run pytest -v -m "not integration"
```

Expected: all pass (18 existing + 10 new auth use case + 7 infra auth = 35 passed).

- [ ] **Step 13: Commit**

```bash
git add src/comptis/infrastructure/auth/ \
  src/comptis/infrastructure/db/repositories.py \
  tests/infrastructure/auth/
git commit -m "feat(infra): add auth infrastructure (bcrypt, JWT, API key lookup)"
```

---

## Task 4: FastAPI Interface Layer

**Files:**
- Create: `src/comptis/interface/api/__init__.py`
- Create: `src/comptis/interface/api/auth/__init__.py`
- Create: `src/comptis/interface/api/auth/schemas.py`
- Create: `src/comptis/interface/api/auth/router.py`
- Create: `src/comptis/interface/api/dependencies.py`
- Create: `src/comptis/interface/api/main.py`

**Interfaces:**
- Consumes: all use cases and infra auth implementations from Tasks 2 and 3
- Produces:
  - `app` — FastAPI application (importable as `comptis.interface.api.main:app`)
  - `get_db_session()` — async generator yielding `AsyncSession` (overridable via `app.dependency_overrides`)
  - `require_user(credentials, session) -> UUID` — FastAPI dependency, sets RLS context, returns user_id
  - `require_api_key(raw_key, session) -> UUID` — FastAPI dependency, sets RLS context, returns org_id

- [ ] **Step 1: Create `__init__.py` files**

```bash
touch src/comptis/interface/api/__init__.py
touch src/comptis/interface/api/auth/__init__.py
```

- [ ] **Step 2: Write Pydantic schemas**

Create `src/comptis/interface/api/auth/schemas.py`:

```python
from uuid import UUID

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    user_id: UUID
    email: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 3: Write dependencies**

Create `src/comptis/interface/api/dependencies.py`:

```python
import functools
import os
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comptis.application.auth.exceptions import InvalidTokenError, TokenExpiredError
from comptis.infrastructure.auth.api_key import get_org_id_for_api_key
from comptis.infrastructure.auth.jwt import JWTTokenService
from comptis.infrastructure.db.tenant_context import set_tenant_context

_bearer = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@functools.lru_cache
def _get_session_factory() -> async_sessionmaker:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncSession:
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            yield session


async def require_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required"},
        )
    try:
        payload = JWTTokenService().decode(credentials.credentials)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Token has expired"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token type"},
        )
    user_id = UUID(payload["sub"])
    await set_tenant_context(session, user_id=user_id)
    return user_id


async def require_api_key(
    raw_key: str = Security(_api_key_header),
    session: AsyncSession = Depends(get_db_session),
) -> UUID:
    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required"},
        )
    org_id = await get_org_id_for_api_key(session, raw_key)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_api_key", "message": "Invalid API key"},
        )
    await set_tenant_context(session, organization_id=org_id)
    return org_id
```

- [ ] **Step 4: Write auth router**

Create `src/comptis/interface/api/auth/router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
)
from comptis.application.auth.use_cases import LoginUser, RefreshToken, RegisterUser
from comptis.infrastructure.auth.jwt import JWTTokenService
from comptis.infrastructure.auth.password import BcryptPasswordHasher
from comptis.infrastructure.db.repositories import SQLAlchemyUserRepository
from comptis.interface.api.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from comptis.interface.api.dependencies import get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: RegisterRequest, session: AsyncSession = Depends(get_db_session)
) -> UserResponse:
    use_case = RegisterUser(
        user_repo=SQLAlchemyUserRepository(session),
        hasher=BcryptPasswordHasher(),
    )
    try:
        user = await use_case.execute(body.email, body.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_already_registered", "message": "Email already in use"},
        )
    return UserResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_db_session)
) -> TokenResponse:
    use_case = LoginUser(
        user_repo=SQLAlchemyUserRepository(session),
        hasher=BcryptPasswordHasher(),
        token_service=JWTTokenService(),
    )
    try:
        access_token, refresh_token = await use_case.execute(body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password"},
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(body: RefreshRequest) -> AccessTokenResponse:
    use_case = RefreshToken(token_service=JWTTokenService())
    try:
        access_token = use_case.execute(body.refresh_token)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "Token has expired"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "Invalid token"},
        )
    return AccessTokenResponse(access_token=access_token)
```

- [ ] **Step 5: Write main FastAPI app**

Create `src/comptis/interface/api/main.py`:

```python
from fastapi import FastAPI

from comptis.interface.api.auth.router import router as auth_router

app = FastAPI(title="Comptis API", version="0.1.0")

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 6: Verify app starts**

```bash
JWT_SECRET_KEY=test-secret-32chars DATABASE_URL=postgresql+asyncpg://x:x@localhost/x \
  uv run python -c "from comptis.interface.api.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add src/comptis/interface/api/
git commit -m "feat(interface): add FastAPI app with auth router and dependencies"
```

---

## Task 5: Integration Tests

**Files:**
- Create: `tests/interface/__init__.py`
- Create: `tests/interface/api/__init__.py`
- Create: `tests/interface/api/conftest.py`
- Create: `tests/interface/api/test_auth.py`

**Interfaces:**
- Consumes: `app` from `comptis.interface.api.main`, `get_db_session` from `comptis.interface.api.dependencies`
- Consumes: testcontainers Postgres + Alembic migration

- [ ] **Step 1: Create `__init__.py` files**

```bash
touch tests/interface/__init__.py
touch tests/interface/api/__init__.py
```

- [ ] **Step 2: Write conftest**

Create `tests/interface/api/conftest.py`:

```python
import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests-32ch")

from comptis.interface.api.dependencies import get_db_session
from comptis.interface.api.main import app


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer(
        "postgres:16", username="postgres", password="test", dbname="comptis_test2"
    ) as pg:
        yield pg


@pytest.fixture(scope="session")
def admin_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+psycopg://postgres:test@{host}:{port}/comptis_test2"


@pytest.fixture(scope="session", autouse=True)
def run_migrations(admin_db_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", admin_db_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_engine(pg_container):
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    url = f"postgresql+asyncpg://comptis_app:app_secret@{host}:{port}/comptis_test2"
    engine = create_async_engine(url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def client(app_engine):
    factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db_session():
        async with factory() as session:
            async with session.begin():
                yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 3: Write failing integration tests**

Create `tests/interface/api/test_auth.py`:

```python
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.integration
async def test_register(client):
    resp = await client.post(
        "/auth/register",
        json={"email": f"user-{uuid4()}@test.fr", "password": "secret123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "user_id" in data
    assert "@test.fr" in data["email"]


@pytest.mark.integration
async def test_register_duplicate_email_returns_409(client):
    email = f"dup-{uuid4()}@test.fr"
    await client.post("/auth/register", json={"email": email, "password": "secret"})
    resp = await client.post("/auth/register", json={"email": email, "password": "secret"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "email_already_registered"


@pytest.mark.integration
async def test_login_returns_tokens(client):
    email = f"login-{uuid4()}@test.fr"
    await client.post("/auth/register", json={"email": email, "password": "secret123"})
    resp = await client.post("/auth/login", json={"email": email, "password": "secret123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.integration
async def test_login_wrong_password_returns_401(client):
    email = f"badpass-{uuid4()}@test.fr"
    await client.post("/auth/register", json={"email": email, "password": "correct"})
    resp = await client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


@pytest.mark.integration
async def test_login_unknown_email_returns_401(client):
    resp = await client.post(
        "/auth/login", json={"email": "nobody@test.fr", "password": "pass"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


@pytest.mark.integration
async def test_refresh_returns_new_access_token(client):
    email = f"refresh-{uuid4()}@test.fr"
    await client.post("/auth/register", json={"email": email, "password": "secret123"})
    login_resp = await client.post("/auth/login", json={"email": email, "password": "secret123"})
    refresh_token = login_resp.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.integration
async def test_refresh_with_invalid_token_returns_401(client):
    resp = await client.post("/auth/refresh", json={"refresh_token": "garbage.token.value"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_token"
```

- [ ] **Step 4: Run integration tests (requires Docker)**

```bash
uv run pytest tests/interface/api/test_auth.py -v -m integration
```

Expected: 8 passed.

- [ ] **Step 5: Run full non-integration suite**

```bash
uv run pytest -v -m "not integration"
```

Expected: 35 passed.

- [ ] **Step 6: Commit**

```bash
git add tests/interface/
git commit -m "test(interface): add auth endpoint integration tests"
```

---

## Self-Review

**Spec coverage:**
- ✅ `POST /auth/register` → Task 2 (use case) + Task 4 (router) + Task 5 (test)
- ✅ `POST /auth/login` → Task 2 + Task 4 + Task 5
- ✅ `POST /auth/refresh` → Task 2 + Task 4 + Task 5
- ✅ `require_user()` dependency → Task 4
- ✅ `require_api_key()` dependency → Task 4
- ✅ Migration 0002 (password_hash + api_keys) → Task 1
- ✅ JWT HS256 with env var secrets → Task 3
- ✅ bcrypt password hashing → Task 3
- ✅ SHA-256 API key hashing → Task 3
- ✅ Error format `{"detail": {"code": ..., "message": ...}}` → Task 4
- ✅ No rate limiting → not implemented (per spec)
- ✅ Unit tests for use cases → Task 2
- ✅ Unit tests for infra (bcrypt, JWT) → Task 3
- ✅ Integration tests via httpx → Task 5

**Type consistency:**
- `AuthUserRepository.save_with_credentials(user: User, password_hash: str)` — used in Task 2 use cases and implemented in Task 3 repos ✅
- `JWTTokenService().decode(token)` — returns `dict`, raises `TokenExpiredError` / `InvalidTokenError` from `application.auth.exceptions` ✅
- `get_org_id_for_api_key(session, raw_key) -> UUID | None` — used in `require_api_key` in Task 4 ✅
- `app.dependency_overrides[get_db_session]` — `get_db_session` exported from `dependencies.py`, imported in `conftest.py` ✅
