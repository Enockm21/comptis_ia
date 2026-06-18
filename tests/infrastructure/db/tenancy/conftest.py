import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

# These engines are session-scoped to avoid re-creating a Postgres container per test.
# Any test module using admin_engine/app_engine/db_session must set
# `pytestmark = pytest.mark.asyncio(loop_scope="session")` or it will hit a
# cross-event-loop RuntimeError from asyncpg.


@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16", username="postgres", password="test", dbname="comptis_test") as pg:
        yield pg


@pytest.fixture(scope="session")
def admin_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    # Explicit psycopg (v3) dialect — psycopg2 is not installed in this project,
    # and relying on the bare "postgresql://" alias to resolve to psycopg3 is
    # not guaranteed across SQLAlchemy versions, so we spell it out.
    return f"postgresql+psycopg://postgres:test@{host}:{port}/comptis_test"


@pytest.fixture(scope="session")
def app_db_url(pg_container) -> str:
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return f"postgresql+asyncpg://comptis_app:app_secret@{host}:{port}/comptis_test"


@pytest.fixture(scope="session", autouse=True)
def run_migrations(admin_db_url):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", admin_db_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def admin_engine(admin_db_url):
    """Superuser engine — bypasses RLS. Use for seeding cross-org test data only."""
    engine = create_async_engine(
        admin_db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://"), echo=False
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def app_engine(app_db_url):
    """comptis_app engine — subject to RLS. Use for all visibility assertions."""
    engine = create_async_engine(app_db_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(app_engine):
    async with AsyncSession(app_engine, expire_on_commit=False) as session:
        async with session.begin():
            yield session
            await session.rollback()
