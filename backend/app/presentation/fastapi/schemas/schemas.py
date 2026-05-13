from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field


# ── Auth / Registration ───────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=10)


class ResendCodeRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
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
    email: EmailStr
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
