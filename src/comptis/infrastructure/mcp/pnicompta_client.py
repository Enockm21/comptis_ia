from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx

from comptis.domain.rapprochement.entities import Facture, Transaction


class PniComptaClient:
    """HTTP client talking to the PNiCompta Django REST API."""

    def __init__(self, base_url: str, token: str, page_size: int = 500) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._page_size = page_size

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    async def list_transactions(
        self,
        statut: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[Transaction]:
        params: dict = {"page_size": self._page_size}
        if date_debut:
            params["start_date"] = date_debut.isoformat()
        if date_fin:
            params["end_date"] = date_fin.isoformat()
        # statut "rapprochee" → has invoices; "non_rapprochee" → no invoices
        if statut == "rapprochee":
            params["reconciled"] = "true"
        elif statut == "non_rapprochee":
            params["reconciled"] = "false"

        data = await self._get("/transactions/", params)
        rows = data.get("results", data) if isinstance(data, dict) else data
        return [self._txn_to_domain(r) for r in rows]

    async def get_transaction(self, id: str) -> Transaction:
        data = await self._get(f"/transactions/{id}/")
        return self._txn_to_domain(data)

    # ------------------------------------------------------------------
    # Factures
    # ------------------------------------------------------------------

    async def list_factures(
        self,
        statut: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[Facture]:
        params: dict = {"page_size": self._page_size}
        if date_debut:
            params["start_date"] = date_debut.isoformat()
        if date_fin:
            params["end_date"] = date_fin.isoformat()
        if statut == "rapprochee":
            params["reconciled"] = "true"
        elif statut == "non_rapprochee":
            params["reconciled"] = "false"

        data = await self._get("/invoices/", params)
        rows = data.get("results", data) if isinstance(data, dict) else data
        return [self._invoice_to_domain(r) for r in rows]

    async def get_facture(self, id: str) -> Facture:
        data = await self._get(f"/invoices/{id}/")
        return self._invoice_to_domain(data)

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    async def mark_rapprochement(
        self,
        facture_id: str,
        transaction_id: str,
        statut: str,
    ) -> None:
        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/invoice-transactions/",
                json={"invoice": int(facture_id), "transaction": int(transaction_id)},
            )
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict | list:
        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            resp = await client.get(f"{self._base}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _txn_to_domain(r: dict) -> Transaction:
        invoices = r.get("invoices") or []
        facture_id = str(invoices[0]["id"]) if invoices else None
        return Transaction(
            id=str(r["id"]),
            montant=Decimal(str(r["amount"])),
            date=date.fromisoformat(r["date"]),
            libelle=r.get("clean_description") or r.get("bank_description") or "",
            facture_id=facture_id,
        )

    @staticmethod
    def _invoice_to_domain(r: dict) -> Facture:
        provider = r.get("provider") or {}
        fournisseur = provider.get("name") or r.get("title") or ""
        billing_date = r.get("billing_date") or r.get("due_date") or ""
        is_reconciled = r.get("is_reconciled", False)
        statut: str
        if is_reconciled:
            statut = "rapprochee"
        elif r.get("is_paid"):
            statut = "rapprochee"
        else:
            statut = "non_rapprochee"

        return Facture(
            id=str(r["id"]),
            montant=Decimal(str(r.get("amount_TTC") or r.get("amount") or "0")),
            date=date.fromisoformat(billing_date) if billing_date else date.today(),
            fournisseur=fournisseur,
            statut_rapprochement=statut,
        )
