from __future__ import annotations
from typing import Protocol
from uuid import UUID
from comptis.domain.integrations.entities import Integration


class IntegrationRepository(Protocol):
    async def list(self, org_id: UUID) -> list[Integration]: ...
    async def get(self, org_id: UUID, name: str) -> Integration | None: ...
    async def upsert(
        self,
        org_id: UUID,
        name: str,
        api_url: str | None,
        mcp_url: str | None,
        token: str | None,
    ) -> Integration: ...
    async def delete(self, org_id: UUID, name: str) -> None: ...
    async def get_decrypted_token(self, org_id: UUID, name: str) -> str | None: ...
