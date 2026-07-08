import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.infrastructure.db.models import ApiKeyModel


async def get_org_id_for_api_key(session: AsyncSession, raw_key: str) -> UUID | None:
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await session.execute(
        select(ApiKeyModel.organization_id).where(ApiKeyModel.key_hash == key_hash)
    )
    return result.scalar_one_or_none()
