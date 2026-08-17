import os

os.environ.setdefault("COMPTIS_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=")

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from comptis.domain.rapprochement.entities import Conflict, Facture, Transaction
from comptis.interface.api.rapprochement.router import _runs

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _seed_run(tenant_id: str, pending_review: list[Conflict]) -> str:
    run_id = str(uuid4())
    _runs[run_id] = {
        "tenant_id": tenant_id,
        "date_debut": date(2026, 1, 1),
        "date_fin": date(2026, 1, 31),
        "pending_review": pending_review,
        "matches": [],
        "unmatched": [],
        "report": None,
    }
    return run_id


@pytest.mark.integration
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.integration
async def test_run_reconciliation_requires_auth(client):
    resp = await client.post("/reconciliation/run", json={"tenant_id": str(uuid4())})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_run_reconciliation_rejects_unknown_tenant(client, admin_token: str):
    resp = await client.post(
        "/reconciliation/run",
        json={"tenant_id": str(uuid4())},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_get_conflicts_requires_auth(client):
    resp = await client.get("/reconciliation/run/nonexistent/conflicts")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_get_conflicts_includes_candidate_facture(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t1", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC SARL")
    facture = Facture(
        id="f1", montant=Decimal("105.00"), date=date(2026, 1, 15),
        fournisseur="ABC SARL", statut_rapprochement="non_rapprochee",
    )
    conflict = Conflict(transaction=transaction, facture=facture, raison="ecart_montant", composite_score=0.8)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/conflicts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["facture"]["fournisseur"] == "ABC SARL"
    assert body[0]["facture"]["montant"] == "105.00"
    assert body[0]["raison"] == "ecart_montant"


@pytest.mark.integration
async def test_get_conflicts_facture_null_when_no_candidate(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t2", montant=Decimal("50.00"), date=date(2026, 1, 15), libelle="MYSTERY")
    conflict = Conflict(transaction=transaction, facture=None, raison="confidence_insuffisante", composite_score=0.4)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/conflicts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()[0]["facture"] is None


@pytest.mark.integration
async def test_get_conflicts_rejects_run_of_inaccessible_tenant(client, admin_tenant_id: str, user_token: str):
    run_id = _seed_run(admin_tenant_id, [])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/conflicts",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_get_conflicts_404_detail_does_not_distinguish_missing_from_inaccessible(
    client, admin_token: str, admin_tenant_id: str, user_token: str
):
    """A caller probing run_ids must not be able to tell 'no such run' apart from
    'run exists but you can't see it' — both cases should 404 with the same body."""
    inaccessible_run_id = _seed_run(admin_tenant_id, [])

    missing_resp = await client.get(
        "/reconciliation/run/does-not-exist/conflicts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    inaccessible_resp = await client.get(
        f"/reconciliation/run/{inaccessible_run_id}/conflicts",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert missing_resp.status_code == 404
    assert inaccessible_resp.status_code == 404
    assert missing_resp.json() == inaccessible_resp.json()


@pytest.mark.integration
async def test_resolve_conflict_confirms_match_and_builds_report(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t3", montant=Decimal("100.00"), date=date(2026, 1, 15), libelle="ABC SARL")
    facture = Facture(
        id="f3", montant=Decimal("100.00"), date=date(2026, 1, 15),
        fournisseur="ABC SARL", statut_rapprochement="non_rapprochee",
    )
    conflict = Conflict(transaction=transaction, facture=facture, raison="confidence_insuffisante", composite_score=0.7)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "t3", "decision": "confirmer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["pending_remaining"] == 0
    assert _runs[run_id]["report"] is not None
    assert _runs[run_id]["report"].total_rapprochees == 1


@pytest.mark.integration
async def test_resolve_conflict_requires_auth(client):
    resp = await client.post(
        "/reconciliation/run/nonexistent/resolve",
        json={"conflict_id": "whatever", "decision": "rejeter"},
    )
    assert resp.status_code == 401


@pytest.mark.integration
async def test_resolve_conflict_rejects_run_of_inaccessible_tenant(client, admin_tenant_id: str, user_token: str):
    run_id = _seed_run(admin_tenant_id, [])

    resp = await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "whatever", "decision": "rejeter"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_get_report_requires_auth(client):
    resp = await client.get("/reconciliation/run/nonexistent/report")
    assert resp.status_code == 401


@pytest.mark.integration
async def test_get_report_rejects_run_of_inaccessible_tenant(client, admin_tenant_id: str, user_token: str):
    run_id = _seed_run(admin_tenant_id, [])

    resp = await client.get(
        f"/reconciliation/run/{run_id}/report",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.integration
async def test_get_report_after_all_conflicts_resolved(client, admin_token: str, admin_tenant_id: str):
    transaction = Transaction(id="t4", montant=Decimal("80.00"), date=date(2026, 1, 15), libelle="XYZ")
    facture = Facture(
        id="f4", montant=Decimal("80.00"), date=date(2026, 1, 15),
        fournisseur="XYZ", statut_rapprochement="non_rapprochee",
    )
    conflict = Conflict(transaction=transaction, facture=facture, raison="ecart_montant", composite_score=0.6)
    run_id = _seed_run(admin_tenant_id, [conflict])
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "t4", "decision": "confirmer"},
        headers=headers,
    )
    resp = await client.get(f"/reconciliation/run/{run_id}/report", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_rapprochees"] == 1
    assert body["total_transactions"] == 1


@pytest.mark.integration
async def test_resolve_confirmer_creates_ecriture_in_db(
    client, admin_token: str, admin_tenant_id: str, admin_db_url: str
):
    from decimal import Decimal
    from sqlalchemy import create_engine, text

    txn = Transaction(id="txn-db-confirmer", montant=Decimal("333.00"), date=date(2026, 2, 1), libelle="CONFIRMER CO")
    fac = Facture(id="fac-db-confirmer", montant=Decimal("333.00"), date=date(2026, 2, 1),
                  fournisseur="CONFIRMER CO", statut_rapprochement="non_rapprochee")
    conflict = Conflict(transaction=txn, facture=fac, raison="confidence_insuffisante", composite_score=0.7)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "txn-db-confirmer", "decision": "confirmer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    eng = create_engine(admin_db_url)
    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT facture_id, montant, statut, compte_id FROM ecritures WHERE transaction_id = :t"),
            {"t": "txn-db-confirmer"},
        ).fetchone()
    eng.dispose()

    assert row is not None, "écriture not written for confirmer decision"
    assert row.facture_id == "fac-db-confirmer"
    assert str(row.montant) == "333.00"
    assert row.statut == "a_categoriser"
    assert row.compte_id is None


@pytest.mark.integration
async def test_resolve_ecart_accepte_creates_ecriture_in_db(
    client, admin_token: str, admin_tenant_id: str, admin_db_url: str
):
    from decimal import Decimal
    from sqlalchemy import create_engine, text

    txn = Transaction(id="txn-db-ecart", montant=Decimal("444.00"), date=date(2026, 2, 2), libelle="ECART CO")
    fac = Facture(id="fac-db-ecart", montant=Decimal("440.00"), date=date(2026, 2, 2),
                  fournisseur="ECART CO", statut_rapprochement="non_rapprochee")
    conflict = Conflict(transaction=txn, facture=fac, raison="ecart_montant", composite_score=0.65)
    run_id = _seed_run(admin_tenant_id, [conflict])

    resp = await client.post(
        f"/reconciliation/run/{run_id}/resolve",
        json={"conflict_id": "txn-db-ecart", "decision": "ecart_accepte"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    eng = create_engine(admin_db_url)
    with eng.connect() as conn:
        row = conn.execute(
            text("SELECT facture_id, montant, statut FROM ecritures WHERE transaction_id = :t"),
            {"t": "txn-db-ecart"},
        ).fetchone()
    eng.dispose()

    assert row is not None, "écriture not written for ecart_accepte decision"
    assert row.facture_id == "fac-db-ecart"
    assert str(row.montant) == "444.00"
    assert row.statut == "a_categoriser"
