from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ReconciliationRunModel


class SQLAlchemyReconciliationRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        *,
        tenant_id: UUID,
        date_debut: date,
        date_fin: date,
        total_transactions: int,
        total_rapprochees: int,
        total_ecarts: int,
        total_non_rapprochees: int,
        statut: str = "termine",
    ) -> ReconciliationRunModel:
        run = ReconciliationRunModel(
            id=uuid4(),
            tenant_id=tenant_id,
            date_debut=date_debut,
            date_fin=date_fin,
            total_transactions=total_transactions,
            total_rapprochees=total_rapprochees,
            total_ecarts=total_ecarts,
            total_non_rapprochees=total_non_rapprochees,
            statut=statut,
            ran_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def list_by_tenant(self, tenant_id: UUID, limit: int = 50) -> list[ReconciliationRunModel]:
        stmt = (
            select(ReconciliationRunModel)
            .where(ReconciliationRunModel.tenant_id == tenant_id)
            .order_by(ReconciliationRunModel.ran_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
