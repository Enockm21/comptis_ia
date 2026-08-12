import os
import uuid as _uuid_module

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests-32ch")

from comptis.interface.api.dependencies import get_db_session  # noqa: E402
from comptis.interface.api.main import app  # noqa: E402


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
async def app_engine(pg_container, run_migrations):
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    url = f"postgresql+asyncpg://comptis_app:app_secret@{host}:{port}/comptis_test2"
    engine = create_async_engine(url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_token(client, admin_db_url) -> str:
    """Register an admin user, seed org+tenant+membership, return JWT."""
    email = f"admin-{_uuid_module.uuid4()}@test.com"
    await client.post("/auth/register", json={"email": email, "password": "Test1234!"})
    resp = await client.post("/auth/login", json={"email": email, "password": "Test1234!"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # Decode JWT to get user_id
    from comptis.infrastructure.auth.jwt import JWTTokenService
    payload = JWTTokenService().decode(token)
    user_id = payload["sub"]

    # Insert org + tenant + membership(role=admin) via postgres superuser
    # admin_db_url is already postgresql+psycopg (sync psycopg3 driver)
    sync_engine = create_engine(admin_db_url)
    org_id = str(_uuid_module.uuid4())
    tenant_id = str(_uuid_module.uuid4())
    membership_id = str(_uuid_module.uuid4())
    with sync_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO organizations(id, name, type, created_at) "
            "VALUES (:id, :name, :type, NOW())"
        ), {"id": org_id, "name": "Test Org", "type": "company"})
        conn.execute(text(
            "INSERT INTO tenants(id, organization_id, name, created_at) "
            "VALUES (:id, :org_id, :name, NOW())"
        ), {"id": tenant_id, "org_id": org_id, "name": "Test Tenant"})
        conn.execute(text(
            "INSERT INTO memberships(id, user_id, tenant_id, role, created_at) "
            "VALUES (:id, :user_id, :tenant_id, :role, NOW())"
        ), {"id": membership_id, "user_id": user_id, "tenant_id": tenant_id, "role": "admin"})
    sync_engine.dispose()

    return token


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def user_token(client) -> str:
    """Register a regular user (no membership) and return JWT."""
    email = f"viewer-{_uuid_module.uuid4()}@test.com"
    await client.post("/auth/register", json={"email": email, "password": "Test1234!"})
    resp = await client.post("/auth/login", json={"email": email, "password": "Test1234!"})
    assert resp.status_code == 200
    return resp.json()["access_token"]
