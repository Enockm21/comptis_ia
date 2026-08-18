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

        # /transactions/ (bare list) has no pagination configured server-side and
        # ignores page_size, returning the entire unpaginated table — times out on
        # real data volume. all_operations/ is the same queryset/filters but paginated.
        data = await self._get("/transactions/all_operations/", params)
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
        # Only ever consider invoices a human has verified — an unverified invoice
        # can carry unreliable OCR-extracted amount/supplier/date data, which would
        # corrupt both candidate matching and the learned pattern memory.
        params: dict = {"page_size": self._page_size, "is_verified": "true"}
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
        amount: Decimal,
    ) -> None:
        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/invoice-transactions/",
                json={
                    "invoice": int(facture_id),
                    "transaction": int(transaction_id),
                    "amount": str(amount),
                },
            )
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # Plan comptable
    # ------------------------------------------------------------------

    async def list_comptes(self) -> list[tuple[str, str]]:
        """Implémente PlanComptableSource — lit toutes les Category configurées
        côté PNiCompta (account_number/account_label réels) en suivant la pagination.
        """
        rows: list[tuple[str, str]] = []
        next_url: str | None = f"{self._base}/categories/"
        params: dict | None = {"page_size": 500}
        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as http:
            while next_url:
                resp = await http.get(next_url, params=params)
                resp.raise_for_status()
                params = None  # only the first request needs page_size
                data = resp.json()
                if isinstance(data, dict):
                    page = data.get("results", data)
                    next_url = data.get("next")
                else:
                    page = data
                    next_url = None
                if not isinstance(page, list):
                    break
                rows.extend(
                    (r["account_number"], r.get("account_label") or r.get("name", ""))
                    for r in page
                    if isinstance(r, dict) and r.get("account_number")
                )
        return rows

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
        statut = "rapprochee" if r.get("is_reconciled", False) else "non_rapprochee"

        return Facture(
            id=str(r["id"]),
            montant=Decimal(str(r.get("amount_TTC") or r.get("amount") or "0")),
            date=date.fromisoformat(billing_date) if billing_date else date.today(),
            fournisseur=fournisseur,
            statut_rapprochement=statut,
            montant_ht=Decimal(str(r.get("amount_HT") or r.get("amount_TTC") or "0")),
            montant_tva=Decimal(str(r.get("amount_tva") or "0")),
            taux_tva=Decimal(str(r.get("tva_rate") or "0")),
            type_facture=str(r.get("invoice_type") or "achat"),
        )
