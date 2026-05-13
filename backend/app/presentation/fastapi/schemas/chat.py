from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


# ── Chat ─────────────────────────────────────────────────────────────────────


class ChatCreateRequest(BaseModel):
    title: str = Field(default="Новый чат", max_length=255)
    credential_id: uuid.UUID | None = None
    model: str | None = None
    system_prompt: str | None = None
    agent_mode: bool = False


class ChatUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    credential_id: uuid.UUID | None = None
    model: str | None = None
    system_prompt: str | None = None
    agent_mode: bool | None = None


class ChatResponse(BaseModel):
    id: uuid.UUID
    title: str
    current_message_id: uuid.UUID | None
    credential_id: uuid.UUID | None
    model: str | None
    system_prompt: str | None
    agent_mode: bool = False


class ChatsListResponse(BaseModel):
    chats: list[ChatResponse]
    total: int


# ── Messages ─────────────────────────────────────────────────────────────────


class MessageResponseDto(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    parent_id: uuid.UUID | None
    role: str
    content: str
    branch_label: str | None
    status: str
    provider: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    error: str | None


class MessagesListResponse(BaseModel):
    messages: list[MessageResponseDto]
    current_message_id: uuid.UUID | None


class SendMessageRequest(BaseModel):
    """
    Послать новое user-сообщение в чат.
    Если parent_id не указан — берём current_message_id чата (= просто реплай).
    Если указан — это форк от конкретного узла.
    """
    content: str = Field(min_length=1, max_length=200_000)
    parent_id: uuid.UUID | None = None


class SwitchBranchRequest(BaseModel):
    message_id: uuid.UUID


class RegenerateRequest(BaseModel):
    from_assistant_message_id: uuid.UUID
    branch_label: str | None = Field(default=None, max_length=60)


class ForkRequest(BaseModel):
    """
    Edit-and-fork: создать новый user-узел с тем же parent, что у указанного
    сообщения (обычно своё же user-сообщение, которое юзер «редактирует»).
    Также может использоваться для произвольного форка от любого узла —
    тогда передаётся любой message_id (даже assistant-сообщение).
    """
    from_message_id: uuid.UUID
    new_content: str = Field(min_length=1, max_length=200_000)
    branch_label: str | None = Field(default=None, max_length=60)
