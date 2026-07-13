from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class RunRequest(BaseModel):
    tenant_id: UUID
    date_debut: date | None = None
    date_fin: date | None = None


class RunResponse(BaseModel):
    run_id: str
    tenant_id: UUID
    date_debut: date
    date_fin: date


class ResolveRequest(BaseModel):
    conflict_id: str
    decision: str  # "confirmer" | "rejeter" | "ecart_accepte"

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        allowed = {"confirmer", "rejeter", "ecart_accepte"}
        if v not in allowed:
            raise ValueError(f"decision must be one of {allowed}")
        return v


class MatchSchema(BaseModel):
    facture_id: str
    transaction_id: str
    confidence: float
    ecart_montant: Decimal
    statut: str


class TransactionSchema(BaseModel):
    id: str
    montant: Decimal
    date: date
    libelle: str


class ConflictSchema(BaseModel):
    transaction: TransactionSchema
    raison: str
    composite_score: float


class ReportResponse(BaseModel):
    tenant_id: UUID
    date_debut: date
    date_fin: date
    total_transactions: int
    total_rapprochees: int
    total_non_rapprochees: int
    total_ecarts: int
    matches: list[MatchSchema]
    unmatched: list[TransactionSchema]
