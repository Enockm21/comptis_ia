from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from comptis.domain.rapprochement.entities import Facture, Transaction

# mcp est une dépendance optionnelle (groupe [mcp] dans pyproject.toml).
# Installez-la avec : uv sync --group mcp
# Elle est importée en lazy dans _call() pour ne pas casser le démarrage
# si PNICOMPTA_MCP_URL n'est pas configuré.


class PniComptaMcpClient:
    """Client MCP (protocol réel) vers le serveur ai-service de PNiCompta.

    Configure MCP_TRANSPORT=streamable-http sur le serveur PNiCompta,
    puis pointe PNICOMPTA_MCP_URL vers http://host:port/mcp.

    Ce client implémente le même contrat que PniComptaClient (HTTP direct)
    mais passe par le protocole MCP — utile pour combiner accès données
    et outils AI dans un même canal.
    """

    def __init__(self, url: str) -> None:
        # ex: http://localhost:8001/mcp
        self._url = url

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    async def list_transactions(
        self,
        statut: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[Transaction]:
        reconciled: bool | None = None
        if statut == "rapprochee":
            reconciled = True
        elif statut == "non_rapprochee":
            reconciled = False

        args: dict = {"limit": 500}
        if date_debut:
            args["start_date"] = date_debut.isoformat()
        if date_fin:
            args["end_date"] = date_fin.isoformat()
        if reconciled is not None:
            args["reconciled"] = reconciled

        rows = await self._call("get_transactions_raw", args)
        return [self._txn_to_domain(r) for r in rows]

    async def get_transaction(self, id: str) -> Transaction:
        rows = await self._call("get_transactions_raw", {"limit": 500})
        for r in rows:
            if str(r.get("id")) == id:
                return self._txn_to_domain(r)
        raise ValueError(f"Transaction {id} non trouvée via MCP")

    # ------------------------------------------------------------------
    # Factures
    # ------------------------------------------------------------------

    async def list_factures(
        self,
        statut: str | None = None,
        date_debut: date | None = None,
        date_fin: date | None = None,
    ) -> list[Facture]:
        is_reconciled: bool | None = None
        if statut == "rapprochee":
            is_reconciled = True
        elif statut == "non_rapprochee":
            is_reconciled = False

        args: dict = {"limit": 500}
        if date_debut:
            args["start_date"] = date_debut.isoformat()
        if date_fin:
            args["end_date"] = date_fin.isoformat()
        if is_reconciled is not None:
            args["is_reconciled"] = is_reconciled

        rows = await self._call("get_invoices_raw", args)
        return [self._invoice_to_domain(r) for r in rows]

    async def get_facture(self, id: str) -> Facture:
        rows = await self._call("get_invoices_raw", {"limit": 500})
        for r in rows:
            if str(r.get("id")) == id:
                return self._invoice_to_domain(r)
        raise ValueError(f"Facture {id} non trouvée via MCP")

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    async def mark_rapprochement(
        self,
        facture_id: str,
        transaction_id: str,
        statut: str,
    ) -> None:
        result = await self._call(
            "link_invoice_transaction",
            {"invoice_id": int(facture_id), "transaction_id": int(transaction_id)},
        )
        if isinstance(result, dict) and not result.get("success"):
            raise RuntimeError(f"MCP link_invoice_transaction: {result.get('error')}")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _call(self, tool_name: str, arguments: dict) -> list | dict:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:
            raise RuntimeError(
                "Le package 'mcp' est requis pour PniComptaMcpClient. "
                "Installez-le avec : uv sync --group mcp"
            ) from exc

        async with streamablehttp_client(self._url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                text = result.content[0].text if result.content else "[]"
                return json.loads(text)

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
        is_reconciled = r.get("is_reconciled", False) or r.get("is_paid", False)
        statut = "rapprochee" if is_reconciled else "non_rapprochee"
        return Facture(
            id=str(r["id"]),
            montant=Decimal(str(r.get("amount_TTC") or r.get("amount") or "0")),
            date=date.fromisoformat(billing_date) if billing_date else date.today(),
            fournisseur=fournisseur,
            statut_rapprochement=statut,
        )
