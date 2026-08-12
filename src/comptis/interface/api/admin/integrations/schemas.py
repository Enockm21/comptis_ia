from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class IntegrationResponse(BaseModel):
    name: str
    api_url: str | None
    mcp_url: str | None
    token_set: bool
    updated_at: datetime


class UpsertIntegrationBody(BaseModel):
    api_url: str | None = None
    mcp_url: str | None = None
    token: str | None = None  # absent = conserver l'existant
