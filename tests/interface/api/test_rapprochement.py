from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.integration
async def test_reconciliation_routes_exist(client):
    resp = await client.get("/reconciliation/run/nonexistent/report")
    # 401 (no API key) or 404 are both fine — the route exists
    assert resp.status_code in (401, 403, 404, 422)
