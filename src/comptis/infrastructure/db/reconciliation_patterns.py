from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.rapprochement.entities import ReconciliationPattern
from comptis.infrastructure.db.models import ReconciliationPatternModel


class SQLAlchemyReconciliationPatternRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_libelle(self, tenant_id: UUID, libelle_pattern: str) -> ReconciliationPattern | None:
        stmt = select(ReconciliationPatternModel).where(
            ReconciliationPatternModel.tenant_id == tenant_id,
            ReconciliationPatternModel.libelle_pattern == libelle_pattern,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    async def upsert(self, pattern: ReconciliationPattern) -> ReconciliationPattern:
        stmt = (
            insert(ReconciliationPatternModel)
            .values(
                id=pattern.id,
                tenant_id=pattern.tenant_id,
                libelle_pattern=pattern.libelle_pattern,
                fournisseur=pattern.fournisseur,
                montant_approx=pattern.montant_approx,
                occurrence_count=pattern.occurrence_count,
                last_seen_at=pattern.last_seen_at,
            )
            .on_conflict_do_update(
                constraint="uq_rp_tenant_libelle_fournisseur",
                set_={
                    "occurrence_count": ReconciliationPatternModel.occurrence_count + 1,
                    "last_seen_at": datetime.now(tz=timezone.utc),
                },
            )
            .returning(ReconciliationPatternModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: ReconciliationPatternModel) -> ReconciliationPattern:
        return ReconciliationPattern(
            id=row.id,
            tenant_id=row.tenant_id,
            libelle_pattern=row.libelle_pattern,
            fournisseur=row.fournisseur,
            montant_approx=Decimal(str(row.montant_approx)),
            occurrence_count=row.occurrence_count,
            last_seen_at=row.last_seen_at,
        )
