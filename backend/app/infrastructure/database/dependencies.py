from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.engine import async_session_maker
from app.infrastructure.database.uow import UnitOfWork


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_uow(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AsyncGenerator[UnitOfWork, None]:
    async with UnitOfWork(session) as uow:
        yield uow
