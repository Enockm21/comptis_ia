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
