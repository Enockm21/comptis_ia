from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class EcritureSchema(BaseModel):
    id: UUID
    libelle: str
    montant: Decimal
    tiers: str
    date: date


class CategorizeRequest(BaseModel):
    tenant_id: UUID
    ecriture: EcritureSchema


class ValidateRequest(BaseModel):
    tenant_id: UUID
    ecriture: EcritureSchema
    compte_code: str


class DecisionResponse(BaseModel):
    id: UUID
    ecriture_id: UUID
    compte_code: str
    statut: str
    confidence: float
    validated_by: UUID | None
    created_at: datetime
