from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class LLMProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class MessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class FileKind(StrEnum):
    TXT = "txt"
    PDF = "pdf"


# ── Данные для LLM-вызова ─────────────────────────────────────────────────────

class LLMMessage(BaseModel):
    """Сообщение в формате, который понимают все провайдеры."""
    role: MessageRole
    content: str


class LLMRequest(BaseModel):
    model: str
    messages: list[LLMMessage]
    system: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


# ── События стрима (унифицированные для всех провайдеров) ────────────────────

class StreamEventType(StrEnum):
    START = "start"
    DELTA = "delta"
    DONE = "done"
    ERROR = "error"


class StreamEvent(BaseModel):
    type: StreamEventType
    text: str | None = None            # для delta
    usage: LLMUsage | None = None      # для done
    error: str | None = None           # для error
    raw: dict[str, Any] | None = None  # сырой ответ провайдера, если нужен


# ── Учётка LLM (юзер хранит свои ключи) ──────────────────────────────────────

class LLMCredential(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    provider: LLMProvider
    label: str                         # «Мой Claude», «Локальный Ollama» и т.п.
    # Для Ollama тут URL, для остальных — ключ (всегда расшифрован в domain-слое)
    secret: str
    base_url: str | None = None        # необязательный кастомный endpoint
    default_model: str | None = None
    is_active: bool = True

    created_at: datetime | None = None
    model_config = {"from_attributes": True}


# ── Узлы графа (для дальнейшего использования) ───────────────────────────────

class ChatNodeStatus(StrEnum):
    PENDING = "pending"      # запрос к LLM ещё идёт
    STREAMING = "streaming"  # стрим в процессе
    READY = "ready"          # ответ получен
    FAILED = "failed"        # ошибка
