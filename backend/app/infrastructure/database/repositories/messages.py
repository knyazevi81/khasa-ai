from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.chat import Message
from app.infrastructure.database.orm.models import Messages
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLMessageRepository(ModelBaseRepository[Messages]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Messages)

    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        result = await self.session.execute(select(Messages).filter_by(id=message_id))
        obj = result.scalar_one_or_none()
        return Message.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> Message | None:
        result = await self.session.execute(select(Messages).filter_by(**filter_by))
        obj = result.scalars().first()
        return Message.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[Message]:
        result = await self.session.execute(select(Messages).filter_by(**filter_by))
        return [Message.model_validate(o) for o in result.scalars().all()]

    async def find_for_chat(self, chat_id: uuid.UUID) -> list[Message]:
        """Все узлы графа этого чата (для отрисовки графа на фронте)."""
        result = await self.session.execute(
            select(Messages)
            .where(Messages.chat_id == chat_id)
            .order_by(Messages.created_at.asc())
        )
        return [Message.model_validate(o) for o in result.scalars().all()]

    async def find_children(self, parent_id: uuid.UUID) -> list[Message]:
        result = await self.session.execute(
            select(Messages)
            .where(Messages.parent_id == parent_id)
            .order_by(Messages.created_at.asc())
        )
        return [Message.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(Messages).values(**data))

    async def update_fields(self, message_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(Messages).where(Messages.id == message_id).values(**fields)
        )

    async def append_content(self, message_id: uuid.UUID, chunk: str) -> None:
        """
        Аккуратное докатывание чанка стрима в `content`.
        Делается отдельным UPDATE-ом, чтобы при обрыве соединения мы не теряли
        собранную часть ответа.
        """
        await self.session.execute(
            update(Messages)
            .where(Messages.id == message_id)
            .values(content=Messages.content + chunk)
        )

    async def get_path_to_root(self, message_id: uuid.UUID) -> list[Message]:
        """
        Возвращает упорядоченный путь от корня к данному узлу.
        Это и есть «активный диалог» для подачи в LLM как messages[]
        (когда user шлёт новое сообщение в ветке).

        Реализуем через рекурсивный CTE — одно обращение к БД.
        """
        from sqlalchemy import text

        sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT * FROM messages WHERE id = :mid
                UNION ALL
                SELECT m.* FROM messages m
                JOIN ancestors a ON m.id = a.parent_id
            )
            SELECT * FROM ancestors
        """)
        result = await self.session.execute(sql, {"mid": message_id})
        rows = result.mappings().all()
        # Идём в обратном порядке: корень → лист
        rows = list(reversed(rows))
        return [Message.model_validate(dict(r)) for r in rows]
