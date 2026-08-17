from __future__ import annotations

import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.integrations.use_cases import GetDecryptedToken
from comptis.infrastructure.db.integration_repository import (
    FernetTokenCipher,
    SQLAlchemyIntegrationRepository,
)
from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient
from comptis.infrastructure.mcp.pnicompta_mcp_client import PniComptaMcpClient


async def build_mcp_client_for_org(
    org_id: uuid.UUID,
    session: AsyncSession,
) -> PniComptaClient | PniComptaMcpClient:
    """Priorité : config DB → fallback env vars.

    Essaie d'abord de charger la config depuis la DB pour 'pnicompta'.
    Si trouvée et decryptable, l'utilise.
    Sinon, fallback sur les variables d'environnement.
    """
    try:
        cipher = FernetTokenCipher.from_env()
    except KeyError:
        cipher = None
    if cipher is not None:
        repo = SQLAlchemyIntegrationRepository(session, cipher)
        token = await GetDecryptedToken(repo).execute(org_id, "pnicompta")
        integ = await repo.get(org_id, "pnicompta")
        if integ is not None:
            if integ.mcp_url:
                return PniComptaMcpClient(url=integ.mcp_url, api_key=token or "")
            if integ.api_url:
                return PniComptaClient(base_url=integ.api_url, token=token or "")

    # Fallback env vars
    mcp_url = os.environ.get("PNICOMPTA_MCP_URL", "")
    api_key = os.environ.get("PNICOMPTA_API_TOKEN", "")
    if mcp_url:
        return PniComptaMcpClient(url=mcp_url, api_key=api_key)
    base_url = os.environ.get("PNICOMPTA_API_URL", "http://localhost:8000/api")
    return PniComptaClient(base_url=base_url, token=api_key)
