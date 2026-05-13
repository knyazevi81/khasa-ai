from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.chat import AgentSubtask, Attachment
from app.infrastructure.database.orm.models import AgentSubtasks, Attachments
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLAttachmentRepository(ModelBaseRepository[Attachments]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Attachments)

    async def get_by_id(self, attachment_id: uuid.UUID) -> Attachment | None:
        result = await self.session.execute(select(Attachments).filter_by(id=attachment_id))
        obj = result.scalar_one_or_none()
        return Attachment.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> Attachment | None:
        result = await self.session.execute(select(Attachments).filter_by(**filter_by))
        obj = result.scalars().first()
        return Attachment.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[Attachment]:
        result = await self.session.execute(select(Attachments).filter_by(**filter_by))
        return [Attachment.model_validate(o) for o in result.scalars().all()]

    async def find_for_message(self, message_id: uuid.UUID) -> list[Attachment]:
        result = await self.session.execute(
            select(Attachments).where(Attachments.message_id == message_id)
        )
        return [Attachment.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(Attachments).values(**data))


class SQLAgentSubtaskRepository(ModelBaseRepository[AgentSubtasks]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AgentSubtasks)

    async def get_by_id(self, subtask_id: uuid.UUID) -> AgentSubtask | None:
        result = await self.session.execute(select(AgentSubtasks).filter_by(id=subtask_id))
        obj = result.scalar_one_or_none()
        return AgentSubtask.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> AgentSubtask | None:
        result = await self.session.execute(select(AgentSubtasks).filter_by(**filter_by))
        obj = result.scalars().first()
        return AgentSubtask.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[AgentSubtask]:
        result = await self.session.execute(select(AgentSubtasks).filter_by(**filter_by))
        return [AgentSubtask.model_validate(o) for o in result.scalars().all()]

    async def find_for_message(self, message_id: uuid.UUID) -> list[AgentSubtask]:
        result = await self.session.execute(
            select(AgentSubtasks)
            .where(AgentSubtasks.message_id == message_id)
            .order_by(AgentSubtasks.order_index.asc())
        )
        return [AgentSubtask.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(AgentSubtasks).values(**data))

    async def update_status(
        self,
        subtask_id: uuid.UUID,
        status: str,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        result: dict | None = None,
    ) -> None:
        values: dict = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if finished_at is not None:
            values["finished_at"] = finished_at
        if result is not None:
            values["result"] = result
        await self.session.execute(
            update(AgentSubtasks)
            .where(AgentSubtasks.id == subtask_id)
            .values(**values)
        )
