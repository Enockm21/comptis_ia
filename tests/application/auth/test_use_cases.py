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
