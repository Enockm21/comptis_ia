from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class ImportPlanComptableRequest(BaseModel):
    tenant_id: UUID


class CompteComptableResponse(BaseModel):
    numero: str
    libelle: str
    classe: int


class ImportPlanComptableResponse(BaseModel):
    comptes: list[CompteComptableResponse]
