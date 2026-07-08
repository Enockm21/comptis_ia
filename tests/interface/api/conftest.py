import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
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
