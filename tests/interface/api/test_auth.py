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
