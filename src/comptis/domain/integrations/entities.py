from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Integration:
    id: UUID
    organization_id: UUID
    name: str
    api_url: str | None
    mcp_url: str | None
    token_set: bool
    updated_at: datetime
