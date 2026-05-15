from __future__ import annotations

import uuid

from sqlalchemy import delete, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.chat import Chat
from app.infrastructure.database.orm.models import Chats
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLChatRepository(ModelBaseRepository[Chats]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Chats)

    async def get_by_id(self, chat_id: uuid.UUID) -> Chat | None:
        result = await self.session.execute(select(Chats).filter_by(id=chat_id))
        obj = result.scalar_one_or_none()
        return Chat.model_validate(obj) if obj else None

    async def get_for_user(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> Chat | None:
        result = await self.session.execute(
            select(Chats).where(Chats.id == chat_id, Chats.user_id == user_id)
        )
        obj = result.scalar_one_or_none()
        return Chat.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> Chat | None:
        result = await self.session.execute(select(Chats).filter_by(**filter_by))
        obj = result.scalars().first()
        return Chat.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[Chat]:
        result = await self.session.execute(select(Chats).filter_by(**filter_by))
        return [Chat.model_validate(o) for o in result.scalars().all()]

    async def find_for_user(
        self, user_id: uuid.UUID, include_hidden: bool = False
    ) -> list[Chat]:
        stmt = select(Chats).where(Chats.user_id == user_id)
        if not include_hidden:
            stmt = stmt.where(Chats.is_hidden == False)  # noqa: E712
        stmt = stmt.order_by(desc(Chats.updated_at))
        result = await self.session.execute(stmt)
        return [Chat.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(Chats).values(**data))

    async def set_current_message(
        self, chat_id: uuid.UUID, message_id: uuid.UUID | None
    ) -> None:
        await self.session.execute(
            update(Chats).where(Chats.id == chat_id).values(current_message_id=message_id)
        )

    async def update_fields(self, chat_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(Chats).where(Chats.id == chat_id).values(**fields)
        )

    async def delete_for_user(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(Chats).where(Chats.id == chat_id, Chats.user_id == user_id)
        )
