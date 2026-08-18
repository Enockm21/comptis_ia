from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateApiKeyRequest(BaseModel):
    name: str


class ApiKeyCreatedResponse(BaseModel):
    id: UUID
    name: str
    key: str  # plain text — shown once only
    created_at: datetime


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime
