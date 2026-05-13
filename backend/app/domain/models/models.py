from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr


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
    id: uuid.UUID
    email: EmailStr
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
