from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class MessageStatus(StrEnum):
    PENDING = "pending"
    STREAMING = "streaming"
    READY = "ready"
    FAILED = "failed"


class SubtaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Attachment(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    filename: str
    kind: str
    size_bytes: int
    extracted_text: str

    model_config = {"from_attributes": True}


class Message(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    parent_id: uuid.UUID | None
    role: str
    content: str
    branch_label: str | None = None
    status: str
    provider: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class Chat(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    current_message_id: uuid.UUID | None = None
    credential_id: uuid.UUID | None = None
    model: str | None = None
    system_prompt: str | None = None
    agent_mode: bool = False
    is_hidden: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentSubtask(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    order_index: int
    title: str
    status: str
    result: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}
