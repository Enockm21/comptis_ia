import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.integration
async def test_import_plan_comptable_requires_auth(client):
    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
async def test_import_plan_comptable_non_admin_gets_403(client, user_token: str, admin_tenant_id: str):
    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": admin_tenant_id},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.integration
async def test_import_plan_comptable_rejects_tenant_of_another_org(client, admin_token: str):
    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_import_plan_comptable_saves_comptes_for_admin(client, admin_token: str, admin_tenant_id: str, monkeypatch):
    from comptis.infrastructure.mcp import client_factory
    from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient

    async def fake_list_comptes(self):
        return [("625100", "Voyages et déplacements"), ("606400", "Fournitures")]

    monkeypatch.setattr(PniComptaClient, "list_comptes", fake_list_comptes)

    async def fake_build_client(org_id, session):
        return PniComptaClient(base_url="http://unused", token="unused")

    monkeypatch.setattr(client_factory, "build_mcp_client_for_org", fake_build_client)
    monkeypatch.setattr(
        "comptis.interface.api.admin.comptabilite.router.build_mcp_client_for_org", fake_build_client,
    )

    resp = await client.post(
        "/admin/comptabilite/import-plan-comptable",
        json={"tenant_id": admin_tenant_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    numeros = {c["numero"] for c in body["comptes"]}
    assert numeros == {"625100", "606400"}
