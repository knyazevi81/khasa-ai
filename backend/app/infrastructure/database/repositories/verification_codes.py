from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.models import VerificationCode
from app.infrastructure.database.orm.models import EmailVerificationCodes
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLVerificationCodeRepository(ModelBaseRepository[EmailVerificationCodes]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmailVerificationCodes)

    async def get_by_id(self, code_id: uuid.UUID) -> VerificationCode | None:
        result = await self.session.execute(
            select(EmailVerificationCodes).filter_by(id=code_id)
        )
        obj = result.scalar_one_or_none()
        return VerificationCode.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> VerificationCode | None:
        result = await self.session.execute(
            select(EmailVerificationCodes).filter_by(**filter_by)
        )
        obj = result.scalars().first()
        return VerificationCode.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[VerificationCode]:
        result = await self.session.execute(
            select(EmailVerificationCodes).filter_by(**filter_by)
        )
        return [VerificationCode.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(EmailVerificationCodes).values(**data))

    async def get_latest_active_for_user(
        self, user_id: uuid.UUID
    ) -> VerificationCode | None:
        """Самый свежий непогашенный код для юзера."""
        result = await self.session.execute(
            select(EmailVerificationCodes)
            .where(
                EmailVerificationCodes.user_id == user_id,
                EmailVerificationCodes.consumed_at.is_(None),
            )
            .order_by(desc(EmailVerificationCodes.created_at))
            .limit(1)
        )
        obj = result.scalar_one_or_none()
        return VerificationCode.model_validate(obj) if obj else None

    async def mark_consumed(self, code_id: uuid.UUID, when: datetime) -> None:
        await self.session.execute(
            update(EmailVerificationCodes)
            .where(EmailVerificationCodes.id == code_id)
            .values(consumed_at=when)
        )

    async def invalidate_for_user(self, user_id: uuid.UUID, when: datetime) -> None:
        """Гасит все активные коды юзера (чтобы старые коды не работали после resend)."""
        await self.session.execute(
            update(EmailVerificationCodes)
            .where(
                EmailVerificationCodes.user_id == user_id,
                EmailVerificationCodes.consumed_at.is_(None),
            )
            .values(consumed_at=when)
        )
