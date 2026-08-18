from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TVALineSchema(BaseModel):
    taux: Decimal
    base_ht: Decimal
    montant_tva: Decimal
    nb_factures: int


class TVAComputeResponse(BaseModel):
    date_debut: date
    date_fin: date
    tva_collectee: Decimal
    tva_deductible: Decimal
    tva_nette: Decimal
    est_credit: bool
    lignes_collectee: list[TVALineSchema]
    lignes_deductible: list[TVALineSchema]


class TVADeclarationCreate(BaseModel):
    tenant_id: UUID
    date_debut: date
    date_fin: date
    tva_collectee: Decimal
    tva_deductible: Decimal
    tva_nette: Decimal
    lignes_collectee: list[TVALineSchema]
    lignes_deductible: list[TVALineSchema]


class TVAStatutUpdate(BaseModel):
    statut: str  # "deposee" | "payee"


class TVADeclarationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    date_debut: date
    date_fin: date
    tva_collectee: Decimal
    tva_deductible: Decimal
    tva_nette: Decimal
    lignes: list[dict]
    statut: str
    created_at: datetime
    deposee_le: datetime | None
    payee_le: datetime | None
