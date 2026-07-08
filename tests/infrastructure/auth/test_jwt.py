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
