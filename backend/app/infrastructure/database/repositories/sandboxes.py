from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.sandbox import Sandbox
from app.infrastructure.database.orm.models import Sandboxes
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLSandboxRepository(ModelBaseRepository[Sandboxes]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Sandboxes)

    async def get_by_id(self, sandbox_id: uuid.UUID) -> Sandbox | None:
        result = await self.session.execute(select(Sandboxes).filter_by(id=sandbox_id))
        obj = result.scalar_one_or_none()
        return Sandbox.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> Sandbox | None:
        result = await self.session.execute(select(Sandboxes).filter_by(**filter_by))
        obj = result.scalars().first()
        return Sandbox.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[Sandbox]:
        result = await self.session.execute(select(Sandboxes).filter_by(**filter_by))
        return [Sandbox.model_validate(o) for o in result.scalars().all()]

    async def get_for_chat(self, chat_id: uuid.UUID) -> Sandbox | None:
        result = await self.session.execute(
            select(Sandboxes).where(Sandboxes.chat_id == chat_id)
        )
        obj = result.scalars().first()
        return Sandbox.model_validate(obj) if obj else None

    async def all_with_users(self) -> list[Sandbox]:
        """Для админ-реестра."""
        result = await self.session.execute(select(Sandboxes))
        return [Sandbox.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(Sandboxes).values(**data))

    async def update_fields(self, sandbox_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(Sandboxes).where(Sandboxes.id == sandbox_id).values(**fields)
        )

    async def remove(self, sandbox_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(Sandboxes).where(Sandboxes.id == sandbox_id)
        )
