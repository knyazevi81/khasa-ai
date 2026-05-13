from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class LLMCredentialCreateRequest(BaseModel):
    provider: str = Field(pattern="^(anthropic|openai|ollama)$")
    label: str = Field(min_length=1, max_length=120)
    secret: str = Field(min_length=0, max_length=500)
    base_url: str | None = None
    default_model: str | None = None


class LLMCredentialUpdateRequest(BaseModel):
    label: str | None = None
    secret: str | None = None     # передавать только если меняешь — иначе оставляем старый
    base_url: str | None = None
    default_model: str | None = None
    is_active: bool | None = None


class LLMCredentialResponse(BaseModel):
    """secret НЕ возвращаем наружу — только маску."""
    id: uuid.UUID
    provider: str
    label: str
    secret_mask: str
    base_url: str | None
    default_model: str | None
    is_active: bool


class LLMCredentialsListResponse(BaseModel):
    credentials: list[LLMCredentialResponse]
    total: int


def mask_secret(secret: str) -> str:
    if not secret:
        return "—"
    if len(secret) <= 8:
        return "*" * len(secret)
    return f"{secret[:4]}…{secret[-4:]}"
