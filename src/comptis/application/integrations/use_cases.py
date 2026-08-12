from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from comptis.application.integrations.ports import IntegrationRepository
from comptis.domain.integrations.entities import Integration


@dataclass
class UpsertIntegrationRequest:
    org_id: UUID
    name: str
    api_url: str | None = None
    mcp_url: str | None = None
    token: str | None = None  # None = conserver le token existant


class ListIntegrations:
    def __init__(self, repo: IntegrationRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: UUID) -> list[Integration]:
        return await self._repo.list(org_id)


class GetIntegration:
    def __init__(self, repo: IntegrationRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: UUID, name: str) -> Integration | None:
        return await self._repo.get(org_id, name)


class UpsertIntegration:
    def __init__(self, repo: IntegrationRepository) -> None:
        self._repo = repo

    async def execute(self, request: UpsertIntegrationRequest) -> Integration:
        return await self._repo.upsert(
            request.org_id, request.name,
            request.api_url, request.mcp_url, request.token,
        )


class DeleteIntegration:
    def __init__(self, repo: IntegrationRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: UUID, name: str) -> None:
        await self._repo.delete(org_id, name)


class GetDecryptedToken:
    def __init__(self, repo: IntegrationRepository) -> None:
        self._repo = repo

    async def execute(self, org_id: UUID, name: str) -> str | None:
        return await self._repo.get_decrypted_token(org_id, name)
