from __future__ import annotations

import uuid

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.orm.models import MCPServers
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLMCPServerRepository(ModelBaseRepository[MCPServers]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MCPServers)

    async def get_by_id(self, server_id: uuid.UUID) -> MCPServers | None:
        result = await self.session.execute(select(MCPServers).filter_by(id=server_id))
        return result.scalar_one_or_none()

    async def find_one_or_none(self, **filter_by) -> MCPServers | None:
        result = await self.session.execute(select(MCPServers).filter_by(**filter_by))
        return result.scalars().first()

    async def find_all(self, **filter_by) -> list[MCPServers]:
        result = await self.session.execute(select(MCPServers).filter_by(**filter_by))
        return list(result.scalars().all())

    async def find_for_user(self, user_id: uuid.UUID) -> list[MCPServers]:
        result = await self.session.execute(
            select(MCPServers).where(MCPServers.user_id == user_id)
        )
        return list(result.scalars().all())

    async def add(self, **data) -> None:
        await self.session.execute(insert(MCPServers).values(**data))

    async def update_fields(self, server_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(MCPServers).where(MCPServers.id == server_id).values(**fields)
        )

    async def delete_for_user(self, server_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(MCPServers).where(
                MCPServers.id == server_id, MCPServers.user_id == user_id
            )
        )
