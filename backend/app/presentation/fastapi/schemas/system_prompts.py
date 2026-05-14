from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SystemPromptResponse(BaseModel):
    id: uuid.UUID
    title: str
    content: str
    description: str | None
    icon: str | None
    is_pinned: bool

    model_config = {"from_attributes": True}


class SystemPromptListResponse(BaseModel):
    prompts: list[SystemPromptResponse]
    total: int


class SystemPromptCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=20000)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=8)


class SystemPromptUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=20000)
    description: str | None = Field(default=None, max_length=300)
    icon: str | None = Field(default=None, max_length=8)
    is_pinned: bool | None = None
