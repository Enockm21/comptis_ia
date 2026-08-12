from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comptis.domain.integrations.entities import Integration
from comptis.infrastructure.db.models import OrgIntegrationModel


class FernetTokenCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        return self._fernet.decrypt(ciphertext).decode()

    @classmethod
    def from_env(cls) -> "FernetTokenCipher":
        key = os.environ["COMPTIS_ENCRYPTION_KEY"]
        return cls(key)


def _to_domain(model: OrgIntegrationModel) -> Integration:
    return Integration(
        id=model.id,
        organization_id=model.organization_id,
        name=model.name,
        api_url=model.api_url,
        mcp_url=model.mcp_url,
        token_set=model.token_encrypted is not None,
        updated_at=model.updated_at,
    )


class SQLAlchemyIntegrationRepository:
    def __init__(self, session: AsyncSession, cipher: FernetTokenCipher) -> None:
        self._session = session
        self._cipher = cipher

    async def list(self, org_id: UUID) -> list[Integration]:
        result = await self._session.execute(
            select(OrgIntegrationModel).where(
                OrgIntegrationModel.organization_id == org_id
            )
        )
        return [_to_domain(m) for m in result.scalars().all()]

    async def get(self, org_id: UUID, name: str) -> Integration | None:
        model = await self._get_model(org_id, name)
        return _to_domain(model) if model else None

    async def upsert(
        self,
        org_id: UUID,
        name: str,
        api_url: str | None,
        mcp_url: str | None,
        token: str | None,
    ) -> Integration:
        model = await self._get_model(org_id, name)
        now = datetime.now(tz=timezone.utc)
        if model is None:
            model = OrgIntegrationModel(
                id=uuid4(),
                organization_id=org_id,
                name=name,
                api_url=api_url,
                mcp_url=mcp_url,
                token_encrypted=self._cipher.encrypt(token) if token else None,
                updated_at=now,
            )
            self._session.add(model)
        else:
            model.api_url = api_url
            model.mcp_url = mcp_url
            if token is not None:
                model.token_encrypted = self._cipher.encrypt(token)
            model.updated_at = now
        await self._session.flush()
        return _to_domain(model)

    async def delete(self, org_id: UUID, name: str) -> None:
        model = await self._get_model(org_id, name)
        if model:
            await self._session.delete(model)
            await self._session.flush()

    async def get_decrypted_token(self, org_id: UUID, name: str) -> str | None:
        model = await self._get_model(org_id, name)
        if model is None or model.token_encrypted is None:
            return None
        return self._cipher.decrypt(model.token_encrypted)

    async def _get_model(
        self, org_id: UUID, name: str
    ) -> OrgIntegrationModel | None:
        result = await self._session.execute(
            select(OrgIntegrationModel).where(
                OrgIntegrationModel.organization_id == org_id,
                OrgIntegrationModel.name == name,
            )
        )
        return result.scalar_one_or_none()
