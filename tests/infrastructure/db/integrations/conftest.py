import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from alembic import command
from alembic.config import Config

# Réutilise pg_container du conftest racine si disponible,
# sinon déclare le fixture ici pour les tests isolés.
# Pour l'instant on réutilise le conftest racine qui tourne les migrations.
