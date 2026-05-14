from __future__ import annotations

import uuid
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, Field


def _validate_email(value: str) -> str:
    """
    Лёгкая валидация e-mail с разрешением «специально-зарезервированных» TLD
    (`.local`, `.test`, `.invalid`, `.localhost`). Это нужно чтобы первый
    суперюзер с `admin@khasa.local` создавался без проблем — и при этом не
    проваливать любую логику, которая загружает такого юзера из БД.
    """
    try:
        result = validate_email(
            value,
            check_deliverability=False,
            allow_smtputf8=True,
            allow_quoted_local=False,
        )
        # Возвращаем нормализованный (lowercased domain) вариант
        return result.normalized
    except EmailNotValidError as exc:
        msg = str(exc).lower()
        # Если email-validator завернул только из-за special-use TLD —
        # пропускаем такой адрес (для локальной разработки).
        if "special-use" in msg or "reserved" in msg:
            return value
        raise ValueError(str(exc)) from exc


# Аннотация-обёртка для всех мест где раньше был EmailStr
EmailAddress = Annotated[str, AfterValidator(_validate_email)]


# ── Auth / Registration ───────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: EmailAddress
    code: str = Field(min_length=4, max_length=10)


class ResendCodeRequest(BaseModel):
    email: EmailAddress


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ── User ─────────────────────────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str                              # уже нормализован
    is_active: bool
    is_email_verified: bool
    is_superuser: bool


class UsersListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class ChangeMyPasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AdminChangePasswordRequest(BaseModel):
    user_id: uuid.UUID
    new_password: str = Field(min_length=8, max_length=128)


# ── Notifications ────────────────────────────────────────────────────────────

class SendToAllRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)


class SendToUserRequest(BaseModel):
    user_id: uuid.UUID
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)


class NotificationSentResponse(BaseModel):
    sent_to: int
    message: str


# ── Misc ─────────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
