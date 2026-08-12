from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TenantSchema(BaseModel):
    id: UUID
    name: str
