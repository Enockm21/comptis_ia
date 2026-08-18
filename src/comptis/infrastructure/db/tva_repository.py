from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.tva.entities import TVADeclaration, TVALine
from comptis.infrastructure.db.models import TVADeclarationModel


class SQLAlchemyTVARepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, declaration: TVADeclaration) -> TVADeclarationModel:
        model = TVADeclarationModel(
            id=declaration.id,
            tenant_id=declaration.tenant_id,
            date_debut=declaration.date_debut,
            date_fin=declaration.date_fin,
            tva_collectee=declaration.tva_collectee,
            tva_deductible=declaration.tva_deductible,
            tva_nette=declaration.tva_nette,
            lignes=declaration.lignes,
            statut=declaration.statut,
            created_at=declaration.created_at,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    async def list_by_tenant(self, tenant_id: UUID) -> list[TVADeclarationModel]:
        result = await self._session.execute(
            select(TVADeclarationModel)
            .where(TVADeclarationModel.tenant_id == tenant_id)
            .order_by(TVADeclarationModel.date_debut.desc())
        )
        return list(result.scalars().all())

    async def get(self, declaration_id: UUID) -> TVADeclarationModel | None:
        result = await self._session.execute(
            select(TVADeclarationModel).where(TVADeclarationModel.id == declaration_id)
        )
        return result.scalar_one_or_none()

    async def update_statut(
        self,
        declaration_id: UUID,
        statut: str,
    ) -> TVADeclarationModel | None:
        model = await self.get(declaration_id)
        if model is None:
            return None
        model.statut = statut
        if statut == "deposee":
            model.deposee_le = datetime.now(tz=timezone.utc)
        elif statut == "payee":
            model.payee_le = datetime.now(tz=timezone.utc)
        await self._session.flush()
        return model
