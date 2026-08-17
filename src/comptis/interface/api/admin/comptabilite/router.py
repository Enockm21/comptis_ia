from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.comptabilite.use_cases import ImporterPlanComptable
from comptis.infrastructure.db.comptabilite_repository import SQLAlchemyCompteComptableRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.infrastructure.mcp.client_factory import build_mcp_client_for_org
from comptis.infrastructure.mcp.pnicompta_client import PniComptaClient
from comptis.interface.api.admin.comptabilite.schemas import (
    CompteComptableResponse,
    ImportPlanComptableRequest,
    ImportPlanComptableResponse,
)
from comptis.interface.api.dependencies import get_db_session, require_admin

router = APIRouter(prefix="/admin/comptabilite", tags=["admin-comptabilite"])


@router.post("/import-plan-comptable", response_model=ImportPlanComptableResponse)
async def import_plan_comptable(
    body: ImportPlanComptableRequest,
    org_id: UUID = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> ImportPlanComptableResponse:
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(body.tenant_id)
    if tenant is None or tenant.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # require_admin leaves app.current_tenant_id at the nil placeholder — plan_comptable
    # and ecritures RLS is keyed on it directly, so it must be set explicitly here.
    await set_tenant_context(session, tenant_id=body.tenant_id)

    client = await build_mcp_client_for_org(org_id, session)
    if not isinstance(client, PniComptaClient):
        raise HTTPException(
            status_code=400,
            detail="Import du plan comptable non supporté en mode MCP pour cette organisation",
        )

    repo = SQLAlchemyCompteComptableRepository(session)
    try:
        comptes = await ImporterPlanComptable(compte_repo=repo, source=client).execute(body.tenant_id)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"PNiCompta unavailable: {exc}")
    return ImportPlanComptableResponse(
        comptes=[
            CompteComptableResponse(numero=c.numero, libelle=c.libelle, classe=c.classe)
            for c in comptes
        ]
    )
