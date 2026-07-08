from dataclasses import dataclass
from uuid import UUID

from comptis.domain.tenancy.entities import User

from .exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidTokenError,
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
        try:
            user_id = UUID(payload["sub"])
        except (ValueError, KeyError):
            raise InvalidTokenError("invalid subject claim")
        return self.token_service.create_access_token(user_id)
