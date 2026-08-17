from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationDecision
from comptis.domain.categorization.value_objects import CategorizationStatut
from comptis.infrastructure.db.models import CategorizationDecisionModel


class SQLAlchemyCategorizationDecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, decision: CategorizationDecision) -> None:
        stmt = (
            insert(CategorizationDecisionModel)
            .values(
                id=decision.id,
                tenant_id=decision.tenant_id,
                ecriture_id=decision.ecriture_id,
                compte_code=decision.compte_code,
                statut=decision.statut.value,
                confidence=decision.confidence,
                validated_by=decision.validated_by,
                created_at=decision.created_at,
            )
            .on_conflict_do_update(
                constraint="uq_cd_ecriture",
                set_={
                    "compte_code": decision.compte_code,
                    "statut": decision.statut.value,
                    "confidence": decision.confidence,
                    "validated_by": decision.validated_by,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_by_ecriture(self, ecriture_id: UUID) -> CategorizationDecision | None:
        result = await self._session.execute(
            select(CategorizationDecisionModel).where(
                CategorizationDecisionModel.ecriture_id == ecriture_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return CategorizationDecision(
            id=row.id,
            tenant_id=row.tenant_id,
            ecriture_id=row.ecriture_id,
            compte_code=row.compte_code,
            statut=CategorizationStatut(row.statut),
            confidence=row.confidence,
            validated_by=row.validated_by,
            created_at=row.created_at,
        )
