from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.categorization.entities import CategorizationPattern
from comptis.infrastructure.db.models import CategorizationPatternModel


class SQLAlchemyCategorizationPatternRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_libelle(self, tenant_id: UUID, libelle_pattern: str) -> CategorizationPattern | None:
        stmt = (
            select(CategorizationPatternModel)
            .where(
                CategorizationPatternModel.tenant_id == tenant_id,
                CategorizationPatternModel.libelle_pattern == libelle_pattern,
            )
            .order_by(
                CategorizationPatternModel.occurrence_count.desc(),
                CategorizationPatternModel.last_seen_at.desc(),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        return self._to_domain(row)

    async def upsert(self, pattern: CategorizationPattern) -> CategorizationPattern:
        stmt = (
            insert(CategorizationPatternModel)
            .values(
                id=pattern.id,
                tenant_id=pattern.tenant_id,
                libelle_pattern=pattern.libelle_pattern,
                fournisseur=pattern.fournisseur,
                compte_code=pattern.compte_code,
                occurrence_count=pattern.occurrence_count,
                last_seen_at=pattern.last_seen_at,
            )
            .on_conflict_do_update(
                constraint="uq_cp_tenant_libelle_fournisseur",
                set_={
                    # A later human correction overrides the compte_code on file, not just
                    # the occurrence count — the accountant is telling us this libelle now
                    # maps to a (possibly different) account.
                    "compte_code": pattern.compte_code,
                    "occurrence_count": CategorizationPatternModel.occurrence_count + 1,
                    "last_seen_at": datetime.now(tz=timezone.utc),
                },
            )
            .returning(CategorizationPatternModel)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: CategorizationPatternModel) -> CategorizationPattern:
        return CategorizationPattern(
            id=row.id,
            tenant_id=row.tenant_id,
            libelle_pattern=row.libelle_pattern,
            fournisseur=row.fournisseur,
            compte_code=row.compte_code,
            occurrence_count=row.occurrence_count,
            last_seen_at=row.last_seen_at,
        )
