import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from comptis.application.integrations.use_cases import (
    DeleteIntegration,
    GetDecryptedToken,
    ListIntegrations,
    UpsertIntegration,
    UpsertIntegrationRequest,
)
from comptis.domain.integrations.entities import Integration


def _make_integration(name: str = "pnicompta") -> Integration:
    return Integration(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), name=name,
        api_url="https://host/api", mcp_url=None, token_set=True,
        updated_at=datetime.now(tz=timezone.utc),
    )


async def test_list_delegates_to_repo():
    repo = AsyncMock()
    org_id = uuid.uuid4()
    repo.list.return_value = [_make_integration()]
    result = await ListIntegrations(repo).execute(org_id)
    repo.list.assert_called_once_with(org_id)
    assert len(result) == 1


async def test_upsert_delegates_to_repo():
    repo = AsyncMock()
    org_id = uuid.uuid4()
    expected = _make_integration()
    repo.upsert.return_value = expected
    req = UpsertIntegrationRequest(
        org_id=org_id, name="pnicompta",
        api_url="https://host/api", mcp_url=None, token="cpt_xxx",
    )
    result = await UpsertIntegration(repo).execute(req)
    repo.upsert.assert_called_once_with(org_id, "pnicompta", "https://host/api", None, "cpt_xxx")
    assert result == expected


async def test_delete_delegates_to_repo():
    repo = AsyncMock()
    org_id = uuid.uuid4()
    await DeleteIntegration(repo).execute(org_id, "pnicompta")
    repo.delete.assert_called_once_with(org_id, "pnicompta")


async def test_get_decrypted_token_delegates_to_repo():
    repo = AsyncMock()
    org_id = uuid.uuid4()
    repo.get_decrypted_token.return_value = "cpt_secret"
    result = await GetDecryptedToken(repo).execute(org_id, "pnicompta")
    assert result == "cpt_secret"
