from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.integrations.use_cases import (
    DeleteIntegration,
    GetIntegration,
    ListIntegrations,
    UpsertIntegration,
    UpsertIntegrationRequest,
)
from comptis.infrastructure.db.integration_repository import (
    FernetTokenCipher,
    SQLAlchemyIntegrationRepository,
)
from comptis.interface.api.admin.integrations.schemas import (
    IntegrationResponse,
    UpsertIntegrationBody,
)
from comptis.interface.api.dependencies import get_db_session, require_admin

router = APIRouter(prefix="/admin/integrations", tags=["admin-integrations"])


def _make_repo(session: AsyncSession) -> SQLAlchemyIntegrationRepository:
    cipher = FernetTokenCipher.from_env()
    return SQLAlchemyIntegrationRepository(session, cipher)


def _to_response(integ) -> IntegrationResponse:
    return IntegrationResponse(
        name=integ.name,
        api_url=integ.api_url,
        mcp_url=integ.mcp_url,
        token_set=integ.token_set,
        updated_at=integ.updated_at,
    )


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    org_id: UUID = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> list[IntegrationResponse]:
    repo = _make_repo(session)
    items = await ListIntegrations(repo).execute(org_id)
    return [_to_response(i) for i in items]


@router.get("/{name}", response_model=IntegrationResponse)
async def get_integration(
    name: str,
    org_id: UUID = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationResponse:
    repo = _make_repo(session)
    integ = await GetIntegration(repo).execute(org_id, name)
    if integ is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    return _to_response(integ)


@router.put("/{name}", response_model=IntegrationResponse)
async def upsert_integration(
    name: str,
    body: UpsertIntegrationBody,
    org_id: UUID = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> IntegrationResponse:
    repo = _make_repo(session)
    integ = await UpsertIntegration(repo).execute(
        UpsertIntegrationRequest(
            org_id=org_id,
            name=name,
            api_url=body.api_url,
            mcp_url=body.mcp_url,
            token=body.token,
        )
    )
    return _to_response(integ)


@router.delete("/{name}", status_code=204)
async def delete_integration(
    name: str,
    org_id: UUID = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    repo = _make_repo(session)
    await DeleteIntegration(repo).execute(org_id, name)
    return Response(status_code=204)
