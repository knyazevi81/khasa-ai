from __future__ import annotations

import uuid

from sqlalchemy import delete, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.orm.models import SystemPrompts
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLSystemPromptRepository(ModelBaseRepository[SystemPrompts]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, SystemPrompts)

    async def get_by_id(self, prompt_id: uuid.UUID) -> SystemPrompts | None:
        result = await self.session.execute(
            select(SystemPrompts).filter_by(id=prompt_id)
        )
        return result.scalar_one_or_none()

    async def find_one_or_none(self, **filter_by) -> SystemPrompts | None:
        result = await self.session.execute(
            select(SystemPrompts).filter_by(**filter_by)
        )
        return result.scalars().first()

    async def find_all(self, **filter_by) -> list[SystemPrompts]:
        result = await self.session.execute(
            select(SystemPrompts).filter_by(**filter_by)
        )
        return list(result.scalars().all())

    async def find_for_user(self, user_id: uuid.UUID) -> list[SystemPrompts]:
        result = await self.session.execute(
            select(SystemPrompts)
            .where(SystemPrompts.user_id == user_id)
            .order_by(desc(SystemPrompts.is_pinned), SystemPrompts.title.asc())
        )
        return list(result.scalars().all())

    async def add(self, **data) -> None:
        await self.session.execute(insert(SystemPrompts).values(**data))

    async def update_fields(self, prompt_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(SystemPrompts).where(SystemPrompts.id == prompt_id).values(**fields)
        )

    async def delete_for_user(self, prompt_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(SystemPrompts).where(
                SystemPrompts.id == prompt_id,
                SystemPrompts.user_id == user_id,
            )
        )
