import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_list_tenants_requires_auth(client):
    resp = await client.get("/tenants")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_list_tenants_returns_only_my_tenants(client, admin_token: str, admin_tenant_id: str):
    resp = await client.get("/tenants", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert admin_tenant_id in ids


@pytest.mark.integration
async def test_list_tenants_empty_for_user_without_membership(client, user_token: str):
    resp = await client.get("/tenants", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    assert resp.json() == []
