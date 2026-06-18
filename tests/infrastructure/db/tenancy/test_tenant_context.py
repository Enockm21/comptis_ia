from uuid import uuid4

import pytest
from sqlalchemy import text

from comptis.infrastructure.db.tenant_context import set_tenant_context


pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_set_organization_id_is_readable(db_session):
    org_id = uuid4()
    await set_tenant_context(db_session, organization_id=org_id)
    result = await db_session.execute(
        text("SELECT current_setting('app.current_organization_id', true)")
    )
    assert result.scalar() == str(org_id)


@pytest.mark.integration
async def test_set_user_id_is_readable(db_session):
    user_id = uuid4()
    await set_tenant_context(db_session, user_id=user_id)
    result = await db_session.execute(
        text("SELECT current_setting('app.current_user_id', true)")
    )
    assert result.scalar() == str(user_id)


@pytest.mark.integration
async def test_unset_variable_returns_empty_string(db_session):
    await set_tenant_context(db_session)  # nothing set
    result = await db_session.execute(
        text("SELECT current_setting('app.current_organization_id', true)")
    )
    assert result.scalar() in (None, "")
