from __future__ import annotations

import uuid

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.llm import LLMCredential
from app.infrastructure.database.orm.models import LLMCredentials
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLLLMCredentialRepository(ModelBaseRepository[LLMCredentials]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LLMCredentials)

    async def get_by_id(self, credential_id: uuid.UUID) -> LLMCredentials | None:
        result = await self.session.execute(
            select(LLMCredentials).filter_by(id=credential_id)
        )
        return result.scalar_one_or_none()

    async def find_one_or_none(self, **filter_by):
        result = await self.session.execute(select(LLMCredentials).filter_by(**filter_by))
        return result.scalars().first()

    async def find_all(self, **filter_by) -> list[LLMCredentials]:
        result = await self.session.execute(select(LLMCredentials).filter_by(**filter_by))
        return list(result.scalars().all())

    async def find_for_user(self, user_id: uuid.UUID) -> list[LLMCredentials]:
        result = await self.session.execute(
            select(LLMCredentials).where(LLMCredentials.user_id == user_id)
        )
        return list(result.scalars().all())

    async def add(self, **data) -> None:
        await self.session.execute(insert(LLMCredentials).values(**data))

    async def update_fields(self, credential_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(LLMCredentials)
            .where(LLMCredentials.id == credential_id)
            .values(**fields)
        )

    async def delete_for_user(self, credential_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(LLMCredentials).where(
                LLMCredentials.id == credential_id,
                LLMCredentials.user_id == user_id,
            )
        )
