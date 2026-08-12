import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_list_integrations_requires_auth(client):
    resp = await client.get("/admin/integrations")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_upsert_and_list_integration(client, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Upsert
    resp = await client.put(
        "/admin/integrations/pnicompta",
        json={"api_url": "https://host/api", "mcp_url": "https://host/mcp", "token": "cpt_test"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "pnicompta"
    assert body["token_set"] is True
    assert "token" not in body  # token jamais expose

    # List
    resp = await client.get("/admin/integrations", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["name"] == "pnicompta" for i in items)


@pytest.mark.integration
async def test_update_without_token_preserves_existing(client, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.put(
        "/admin/integrations/myapp",
        json={"api_url": "https://a.com/api", "token": "original"},
        headers=headers,
    )
    # Update URL sans token
    resp = await client.put(
        "/admin/integrations/myapp",
        json={"api_url": "https://b.com/api"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["token_set"] is True  # token conserve


@pytest.mark.integration
async def test_delete_integration(client, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.put("/admin/integrations/todelete", json={}, headers=headers)
    resp = await client.delete("/admin/integrations/todelete", headers=headers)
    assert resp.status_code == 204
    # Verify the row is actually gone
    list_resp = await client.get("/admin/integrations", headers=headers)
    assert not any(i["name"] == "todelete" for i in list_resp.json())


@pytest.mark.integration
async def test_non_admin_gets_403(client, user_token: str):
    resp = await client.get(
        "/admin/integrations",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403
