from __future__ import annotations

import uuid

from app.domain.exceptions.base import (
    ForbiddenError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from app.domain.interface.email import AbstractEmailService
from app.domain.models.models import User
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.security.password import BcryptPasswordHasher


class UserService:
    """
    Сценарии управления пользователями (свой профиль + админские операции).
    """

    def __init__(
        self,
        uow: UnitOfWork,
        password_hasher: BcryptPasswordHasher,
        email_service: AbstractEmailService,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.email_service = email_service

    # ── Свой профиль ─────────────────────────────────────────────────────────

    async def get_me(self, user_id: uuid.UUID) -> User:
        user = await self.uow.users.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def change_my_password(
        self, current_user: User, old_password: str, new_password: str
    ) -> None:
        hashed_password = await self.uow.users.get_hashed_password(current_user.email)
        if not self.password_hasher.verify(old_password, hashed_password):
            raise InvalidCredentialsError("Неверный текущий пароль")

        new_hashed = self.password_hasher.hash(new_password)
        await self.uow.users.change_password(current_user.id, new_hashed)
        await self.email_service.send_password_changed(current_user.email)

    # ── Админ ────────────────────────────────────────────────────────────────

    async def get_all_users(self, current_user: User) -> list[User]:
        self._require_admin(current_user)
        return await self.uow.users.find_all()

    async def get_pending_users(self, current_user: User) -> list[User]:
        """
        Список юзеров, ожидающих одобрения: email подтверждён, но is_active=False.
        Юзеры, которые ещё не подтвердили email, в админский список не попадают.
        """
        self._require_admin(current_user)
        all_inactive = await self.uow.users.find_all(is_active=False)
        return [u for u in all_inactive if u.is_email_verified]

    async def activate_user(self, user_id: uuid.UUID, current_user: User) -> User:
        self._require_admin(current_user)
        user = await self.uow.users.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        # Защита от случайного аппрува юзера с неподтверждённым email
        if not user.is_email_verified:
            raise ForbiddenError("Сначала юзер должен подтвердить email")

        await self.uow.users.activate(user_id)
        await self.email_service.send_account_activated(user.email)

        return User(
            id=user.id,
            email=user.email,
            is_email_verified=user.is_email_verified,
            is_active=True,
            is_superuser=user.is_superuser,
        )

    async def deactivate_user(self, user_id: uuid.UUID, current_user: User) -> User:
        self._require_admin(current_user)
        user = await self.uow.users.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        if user.id == current_user.id:
            raise ForbiddenError("Нельзя деактивировать самого себя")

        await self.uow.users.deactivate(user_id)
        return User(
            id=user.id,
            email=user.email,
            is_email_verified=user.is_email_verified,
            is_active=False,
            is_superuser=user.is_superuser,
        )

    async def admin_change_password(
        self,
        user_id: uuid.UUID,
        new_password: str,
        current_user: User,
    ) -> None:
        self._require_admin(current_user)
        user = await self.uow.users.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        hashed = self.password_hasher.hash(new_password)
        await self.uow.users.change_password(user_id, hashed)
        await self.email_service.send_password_changed(user.email)

    # ── Рассылка ─────────────────────────────────────────────────────────────

    async def send_notification_to_all(
        self, subject: str, message: str, current_user: User
    ) -> int:
        self._require_admin(current_user)
        all_users = await self.uow.users.find_all(is_active=True)
        emails = [u.email for u in all_users if not u.is_superuser]
        if emails:
            await self.email_service.send_custom(emails, subject, message)
        return len(emails)

    async def send_notification_to_user(
        self,
        user_id: uuid.UUID,
        subject: str,
        message: str,
        current_user: User,
    ) -> None:
        self._require_admin(current_user)
        user = await self.uow.users.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        await self.email_service.send_custom(user.email, subject, message)

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _require_admin(current_user: User) -> None:
        if not current_user.is_superuser:
            raise ForbiddenError()
