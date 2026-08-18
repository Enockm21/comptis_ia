from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

from comptis.application.rapprochement.ports import McpClient
from comptis.domain.tva.entities import TVADeclaration, TVALine, TVASummary


class ComputeTVA:
    def __init__(self, mcp_client: McpClient) -> None:
        self._client = mcp_client

    async def execute(
        self,
        tenant_id: UUID,
        date_debut: date,
        date_fin: date,
    ) -> TVASummary:
        factures = await self._client.list_factures(
            date_debut=date_debut,
            date_fin=date_fin,
            verified_only=True,
        )

        # Group by taux for collectée (vente) and déductible (achat)
        collectee_by_taux: dict[Decimal, dict] = defaultdict(lambda: {"base_ht": Decimal("0"), "tva": Decimal("0"), "n": 0})
        deductible_by_taux: dict[Decimal, dict] = defaultdict(lambda: {"base_ht": Decimal("0"), "tva": Decimal("0"), "n": 0})

        for f in factures:
            bucket = collectee_by_taux if f.type_facture == "vente" else deductible_by_taux
            taux = f.taux_tva.quantize(Decimal("0.01"))
            bucket[taux]["base_ht"] += f.montant_ht
            bucket[taux]["tva"] += f.montant_tva
            bucket[taux]["n"] += 1

        def to_lines(bucket: dict) -> list[TVALine]:
            return sorted(
                [TVALine(taux=t, base_ht=v["base_ht"], montant_tva=v["tva"], nb_factures=v["n"])
                 for t, v in bucket.items()],
                key=lambda l: l.taux, reverse=True,
            )

        lignes_collectee = to_lines(collectee_by_taux)
        lignes_deductible = to_lines(deductible_by_taux)

        return TVASummary(
            tva_collectee=sum((l.montant_tva for l in lignes_collectee), Decimal("0")),
            tva_deductible=sum((l.montant_tva for l in lignes_deductible), Decimal("0")),
            lignes_collectee=lignes_collectee,
            lignes_deductible=lignes_deductible,
        )
