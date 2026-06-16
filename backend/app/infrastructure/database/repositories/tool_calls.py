from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.orm.models import ToolCalls
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLToolCallRepository(ModelBaseRepository[ToolCalls]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ToolCalls)

    async def get_by_id(self, call_id: uuid.UUID) -> ToolCalls | None:
        result = await self.session.execute(
            select(ToolCalls).filter_by(id=call_id)
        )
        return result.scalar_one_or_none()

    async def find_one_or_none(self, **filter_by) -> ToolCalls | None:
        result = await self.session.execute(select(ToolCalls).filter_by(**filter_by))
        return result.scalars().first()

    async def find_all(self, **filter_by) -> list[ToolCalls]:
        result = await self.session.execute(select(ToolCalls).filter_by(**filter_by))
        return list(result.scalars().all())

    async def find_for_message(self, message_id: uuid.UUID) -> list[ToolCalls]:
        result = await self.session.execute(
            select(ToolCalls)
            .where(ToolCalls.message_id == message_id)
            .order_by(ToolCalls.order_idx.asc())
        )
        return list(result.scalars().all())

    async def find_for_messages(
        self, message_ids: list[uuid.UUID]
    ) -> list[ToolCalls]:
        """Батч-загрузка для message-list endpoint — без N+1."""
        if not message_ids:
            return []
        result = await self.session.execute(
            select(ToolCalls)
            .where(ToolCalls.message_id.in_(message_ids))
            .order_by(ToolCalls.message_id, ToolCalls.order_idx.asc())
        )
        return list(result.scalars().all())

    async def add(self, **data) -> None:
        await self.session.execute(insert(ToolCalls).values(**data))

    async def update_fields(self, call_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(ToolCalls).where(ToolCalls.id == call_id).values(**fields)
        )
