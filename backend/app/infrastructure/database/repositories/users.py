from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.models import User
from app.infrastructure.database.orm.models import Users
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLUserRepository(ModelBaseRepository[Users]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Users)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(Users).filter_by(id=user_id))
        obj = result.scalar_one_or_none()
        return User.model_validate(obj) if obj else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(Users).filter_by(email=email))
        obj = result.scalar_one_or_none()
        return User.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> User | None:
        result = await self.session.execute(select(Users).filter_by(**filter_by))
        obj = result.scalars().first()
        return User.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[User]:
        result = await self.session.execute(select(Users).filter_by(**filter_by))
        return [User.model_validate(obj) for obj in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(Users).values(**data))

    async def mark_email_verified(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Users).where(Users.id == user_id).values(is_email_verified=True)
        )

    async def activate(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Users).where(Users.id == user_id).values(is_active=True)
        )

    async def deactivate(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Users).where(Users.id == user_id).values(is_active=False)
        )

    async def change_password(self, user_id: uuid.UUID, hashed_password: str) -> None:
        await self.session.execute(
            update(Users)
            .where(Users.id == user_id)
            .values(hashed_password=hashed_password)
        )

    async def get_hashed_password(self, email: str) -> str | None:
        result = await self.session.execute(
            select(Users.hashed_password).filter_by(email=email)
        )
        return result.scalar_one_or_none()

    async def set_superuser(self, user_id: uuid.UUID, is_superuser: bool) -> None:
        await self.session.execute(
            update(Users).where(Users.id == user_id).values(is_superuser=is_superuser)
        )
