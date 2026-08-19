from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TenantSchema(BaseModel):
    id: UUID
    name: str
    siret: str | None = None
    numero_tva: str | None = None
    adresse: str | None = None
    code_postal_ville: str | None = None


class TenantInfoUpdate(BaseModel):
    siret: str | None = None
    numero_tva: str | None = None
    adresse: str | None = None
    code_postal_ville: str | None = None
