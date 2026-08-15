import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _ecriture_payload(libelle="TOULOUSE SELF STOCKAGE", tiers="Toulouse Self Stockage"):
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "libelle": libelle,
        "montant": "90.00",
        "tiers": tiers,
        "date": "2024-02-08",
    }


@pytest.mark.integration
async def test_categorize_requires_auth(client):
    resp = await client.post("/categorization/categorize", json={
        "tenant_id": "22222222-2222-2222-2222-222222222222",
        "ecriture": _ecriture_payload(),
    })
    assert resp.status_code == 401


@pytest.mark.integration
async def test_categorize_rejects_unknown_tenant(client, admin_token: str):
    resp = await client.post(
        "/categorization/categorize",
        json={
            "tenant_id": "22222222-2222-2222-2222-222222222222",
            "ecriture": _ecriture_payload(),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_categorize_returns_a_decision(client, admin_token: str, admin_tenant_id: str):
    resp = await client.post(
        "/categorization/categorize",
        json={"tenant_id": admin_tenant_id, "ecriture": _ecriture_payload()},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["statut"] in ("auto_validated", "pending_review")
    assert "id" in body


@pytest.mark.integration
async def test_validate_after_categorize_learns_pattern(client, admin_token: str, admin_tenant_id: str):
    payload = _ecriture_payload(libelle="SIEMENS LEASE 02", tiers="Siemens Lease")
    payload["id"] = "33333333-3333-3333-3333-333333333333"

    cat_resp = await client.post(
        "/categorization/categorize",
        json={"tenant_id": admin_tenant_id, "ecriture": payload},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cat_resp.status_code == 200

    val_resp = await client.post(
        "/categorization/validate",
        json={"tenant_id": admin_tenant_id, "ecriture": payload, "compte_code": "613500"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert val_resp.status_code == 200
    body = val_resp.json()
    assert body["statut"] == "human_validated"
    assert body["compte_code"] == "613500"
    assert body["validated_by"] is not None


@pytest.mark.integration
async def test_validate_unknown_ecriture_returns_404(client, admin_token: str, admin_tenant_id: str):
    payload = _ecriture_payload()
    payload["id"] = "44444444-4444-4444-4444-444444444444"
    resp = await client.post(
        "/categorization/validate",
        json={"tenant_id": admin_tenant_id, "ecriture": payload, "compte_code": "613500"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
