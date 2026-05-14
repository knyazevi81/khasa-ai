from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


# ── Auth tokens ───────────────────────────────────────────────────────────────

class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    type: TokenType
    exp: int


# ── User ──────────────────────────────────────────────────────────────────────

class User(BaseModel):
    """
    Доменная модель юзера.

    `email` — обычная строка, а не `EmailStr`: формат уже провалидирован
    при регистрации (см. `RegisterRequest` в presentation-схемах). Здесь
    мы загружаем уже сохранённую запись из БД и не должны падать на
    специально-зарезервированных TLD типа `.local`, которые приходят, например,
    от первого суперюзера, созданного через `make superuser`.
    """
    id: uuid.UUID
    email: str
    is_active: bool                  # одобрен админом — может логиниться
    is_email_verified: bool          # подтвердил email кодом
    is_superuser: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Email verification ────────────────────────────────────────────────────────

class VerificationCode(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    code_hash: str                   # bcrypt-хэш самого кода
    expires_at: datetime
    consumed_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
