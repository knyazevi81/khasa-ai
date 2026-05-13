from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.domain.exceptions.base import (
    EmailAlreadyVerifiedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserInactiveError,
    UserNotFoundError,
    VerificationCodeCooldownError,
    VerificationCodeInvalidError,
)
from app.domain.interface.email import AbstractEmailService
from app.domain.models.models import TokenPair, User
from app.infrastructure.config.config import Settings
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.security.codes import generate_numeric_code
from app.infrastructure.security.jwt import JoseTokenService
from app.infrastructure.security.password import BcryptPasswordHasher


class AuthService:
    """
    Сценарии аутентификации и регистрации.

    Flow регистрации:
      register()            → юзер: is_email_verified=False, is_active=False
                              → отправлен 6-значный код, статус 201
      verify_email_code()   → is_email_verified=True (всё ещё is_active=False)
                              → юзеру письмо «заявка отправлена», админу — pending
      (админ нажимает «активировать»)
      login()               → проверяет, что email подтверждён и админ одобрил
    """

    def __init__(
        self,
        uow: UnitOfWork,
        password_hasher: BcryptPasswordHasher,
        token_service: JoseTokenService,
        email_service: AbstractEmailService,
        settings: Settings,
    ) -> None:
        self.uow = uow
        self.password_hasher = password_hasher
        self.token_service = token_service
        self.email_service = email_service
        self.settings = settings

    # ── Регистрация ──────────────────────────────────────────────────────────

    async def register(self, email: str, password: str) -> User:
        existing = await self.uow.users.get_by_email(email)
        if existing:
            # Не подсказываем атакующему, что email занят — но честно говорим
            # самому юзеру, если он пытается перерегистрироваться. Тут предпочли
            # явную ошибку: для админ-сценария это важнее, чем enumeration-leak.
            raise UserAlreadyExistsError()

        hashed = self.password_hasher.hash(password)
        user_id = uuid.uuid4()

        await self.uow.users.add(
            id=user_id,
            email=email,
            hashed_password=hashed,
            is_email_verified=False,
            is_active=False,
            is_superuser=False,
        )

        # И сразу выпускаем код для подтверждения email
        await self._issue_and_send_code(user_id=user_id, email=email)

        return User(
            id=user_id,
            email=email,
            is_email_verified=False,
            is_active=False,
            is_superuser=False,
        )

    async def resend_verification_code(self, email: str) -> None:
        user = await self.uow.users.get_by_email(email)
        if not user:
            # Не светим существование email-а во внешний мир
            return
        if user.is_email_verified:
            raise EmailAlreadyVerifiedError()

        latest = await self.uow.verification_codes.get_latest_active_for_user(user.id)
        if latest:
            elapsed = datetime.now(timezone.utc) - latest.created_at.replace(tzinfo=timezone.utc) \
                if latest.created_at and latest.created_at.tzinfo is None else \
                datetime.now(timezone.utc) - latest.created_at
            if elapsed < timedelta(seconds=self.settings.VERIFICATION_RESEND_COOLDOWN_SECONDS):
                raise VerificationCodeCooldownError()

        await self._issue_and_send_code(user_id=user.id, email=user.email)

    async def verify_email_code(self, email: str, code: str) -> User:
        user = await self.uow.users.get_by_email(email)
        if not user:
            raise VerificationCodeInvalidError()
        if user.is_email_verified:
            raise EmailAlreadyVerifiedError()

        latest = await self.uow.verification_codes.get_latest_active_for_user(user.id)
        if not latest:
            raise VerificationCodeInvalidError()

        # Проверяем срок жизни кода
        now = datetime.now(timezone.utc)
        expires_at = latest.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now >= expires_at:
            raise VerificationCodeInvalidError()

        # Проверяем сам код (хэш)
        if not self.password_hasher.verify(code, latest.code_hash):
            raise VerificationCodeInvalidError()

        # Гасим все коды этого юзера и помечаем email как подтверждённый
        await self.uow.verification_codes.invalidate_for_user(user.id, when=now)
        await self.uow.users.mark_email_verified(user.id)

        # Письмо «заявка отправлена, ждите админа»
        await self.email_service.send_registration_pending_approval(user.email)

        return User(
            id=user.id,
            email=user.email,
            is_email_verified=True,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
        )

    # ── Логин ────────────────────────────────────────────────────────────────

    async def login(self, email: str, password: str) -> TokenPair:
        user = await self.uow.users.get_by_email(email)
        if not user:
            raise InvalidCredentialsError()

        hashed_password = await self.uow.users.get_hashed_password(email)
        if not self.password_hasher.verify(password, hashed_password):
            raise InvalidCredentialsError()

        if not user.is_email_verified:
            raise EmailNotVerifiedError()

        if not user.is_active:
            raise UserInactiveError()

        return self.token_service.create_pair(str(user.id))

    async def refresh(self, refresh_token: str) -> TokenPair:
        payload = self.token_service.decode_refresh(refresh_token)
        # Дополнительно проверим, что юзер ещё жив и активен
        user = await self.uow.users.get_by_id(uuid.UUID(payload.sub))
        if not user or not user.is_active:
            raise InvalidCredentialsError()
        return self.token_service.create_pair(payload.sub)

    async def get_current_user(self, access_token: str) -> User:
        payload = self.token_service.decode_access(access_token)
        user = await self.uow.users.get_by_id(uuid.UUID(payload.sub))
        if not user:
            raise UserNotFoundError()
        if not user.is_active:
            raise UserInactiveError()
        return user

    # ── private ──────────────────────────────────────────────────────────────

    async def _issue_and_send_code(self, *, user_id: uuid.UUID, email: str) -> None:
        # Все ранее выданные коды юзера гасим
        now = datetime.now(timezone.utc)
        await self.uow.verification_codes.invalidate_for_user(user_id, when=now)

        code_plain = generate_numeric_code(self.settings.VERIFICATION_CODE_LENGTH)
        code_hash = self.password_hasher.hash(code_plain)
        expires_at = now + timedelta(minutes=self.settings.VERIFICATION_CODE_TTL_MINUTES)

        await self.uow.verification_codes.add(
            id=uuid.uuid4(),
            user_id=user_id,
            code_hash=code_hash,
            expires_at=expires_at,
        )

        await self.email_service.send_verification_code(
            to=email,
            code=code_plain,
            ttl_minutes=self.settings.VERIFICATION_CODE_TTL_MINUTES,
        )
