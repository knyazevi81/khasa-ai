from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.orm.models import MessageTextSegments
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLMessageTextSegmentRepository(ModelBaseRepository[MessageTextSegments]):
    """
    Сегменты текста ассистент-сообщения, чередующиеся с tool_calls.
    Используется для рендера «text → tool → text → tool → ...» в порядке
    появления, а не «весь текст сверху, все tool снизу».
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MessageTextSegments)

    async def get_by_id(self, seg_id: uuid.UUID) -> MessageTextSegments | None:
        result = await self.session.execute(
            select(MessageTextSegments).filter_by(id=seg_id)
        )
        return result.scalar_one_or_none()

    async def find_one_or_none(self, **filter_by) -> MessageTextSegments | None:
        result = await self.session.execute(
            select(MessageTextSegments).filter_by(**filter_by)
        )
        return result.scalars().first()

    async def find_all(self, **filter_by) -> list[MessageTextSegments]:
        result = await self.session.execute(
            select(MessageTextSegments).filter_by(**filter_by)
        )
        return list(result.scalars().all())

    async def find_for_message(
        self, message_id: uuid.UUID
    ) -> list[MessageTextSegments]:
        result = await self.session.execute(
            select(MessageTextSegments)
            .where(MessageTextSegments.message_id == message_id)
            .order_by(MessageTextSegments.order_idx.asc())
        )
        return list(result.scalars().all())

    async def find_for_messages(
        self, message_ids: list[uuid.UUID]
    ) -> list[MessageTextSegments]:
        if not message_ids:
            return []
        result = await self.session.execute(
            select(MessageTextSegments)
            .where(MessageTextSegments.message_id.in_(message_ids))
            .order_by(MessageTextSegments.message_id, MessageTextSegments.order_idx.asc())
        )
        return list(result.scalars().all())

    async def add(self, **data) -> None:
        await self.session.execute(insert(MessageTextSegments).values(**data))

    async def append_content(self, seg_id: uuid.UUID, chunk: str) -> None:
        """
        Дописывает к существующему сегменту чанк (используется при стриминге —
        каждые ~32 символа). Через CONCAT чтобы не делать SELECT+UPDATE.
        """
        await self.session.execute(
            update(MessageTextSegments)
            .where(MessageTextSegments.id == seg_id)
            .values(content=MessageTextSegments.content.op("||")(chunk))
        )
