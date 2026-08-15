from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.application.categorization.use_cases import CategorizeEcriture, ValidateCategorization
from comptis.domain.categorization.entities import CategorizationDecision, EcritureACategoriser
from comptis.domain.categorization.exceptions import CategorizationDecisionNotFoundError
from comptis.infrastructure.categorization.rapidfuzz_retriever import RapidFuzzAccountRetriever
from comptis.infrastructure.db.categorization_decisions import SQLAlchemyCategorizationDecisionRepository
from comptis.infrastructure.db.categorization_patterns import SQLAlchemyCategorizationPatternRepository
from comptis.infrastructure.db.repositories import SQLAlchemyTenantRepository
from comptis.infrastructure.db.tenant_context import set_tenant_context
from comptis.interface.api.categorization.schemas import (
    CategorizeRequest,
    DecisionResponse,
    ValidateRequest,
)
from comptis.interface.api.dependencies import get_db_session, require_user

router = APIRouter(prefix="/categorization", tags=["categorization"])


async def _require_tenant_access(tenant_id: uuid.UUID, session: AsyncSession):
    tenant = await SQLAlchemyTenantRepository(session).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _to_response(decision: CategorizationDecision) -> DecisionResponse:
    return DecisionResponse(
        id=decision.id,
        ecriture_id=decision.ecriture_id,
        compte_code=decision.compte_code,
        statut=decision.statut.value,
        confidence=decision.confidence,
        validated_by=decision.validated_by,
        created_at=decision.created_at,
    )


def _to_domain_ecriture(body_ecriture) -> EcritureACategoriser:
    return EcritureACategoriser(
        id=body_ecriture.id,
        libelle=body_ecriture.libelle,
        montant=body_ecriture.montant,
        tiers=body_ecriture.tiers,
        date=body_ecriture.date,
    )


@router.post("/categorize", response_model=DecisionResponse)
async def categorize(
    body: CategorizeRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    tenant = await _require_tenant_access(body.tenant_id, session)
    await set_tenant_context(
        session, organization_id=tenant.organization_id, tenant_id=body.tenant_id, user_id=user_id
    )
    use_case = CategorizeEcriture(
        pattern_repo=SQLAlchemyCategorizationPatternRepository(session),
        account_retriever=await RapidFuzzAccountRetriever.load(session),
        decision_repo=SQLAlchemyCategorizationDecisionRepository(session),
    )
    decision = await use_case.execute(tenant_id=body.tenant_id, ecriture=_to_domain_ecriture(body.ecriture))
    return _to_response(decision)


@router.post("/validate", response_model=DecisionResponse)
async def validate(
    body: ValidateRequest,
    user_id: uuid.UUID = Depends(require_user),
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    tenant = await _require_tenant_access(body.tenant_id, session)
    await set_tenant_context(
        session, organization_id=tenant.organization_id, tenant_id=body.tenant_id, user_id=user_id
    )
    retriever = await RapidFuzzAccountRetriever.load(session)
    if not any(c.code == body.compte_code for c in retriever.comptes):
        raise HTTPException(status_code=422, detail="Unknown compte_code")
    use_case = ValidateCategorization(
        pattern_repo=SQLAlchemyCategorizationPatternRepository(session),
        decision_repo=SQLAlchemyCategorizationDecisionRepository(session),
    )
    try:
        decision = await use_case.execute(
            tenant_id=body.tenant_id,
            ecriture=_to_domain_ecriture(body.ecriture),
            compte_code=body.compte_code,
            validated_by=user_id,
        )
    except CategorizationDecisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _to_response(decision)
