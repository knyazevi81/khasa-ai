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
    """
    Сообщение в формате, который понимают все провайдеры.

    Контент может быть:
      • строкой — обычный текст;
      • списком блоков — для tool use (text-блоки + tool_use + tool_result).
        Это нужно когда LLM в одном ответе пишет «сейчас сделаю X» и сразу
        вызывает инструмент.
    """
    role: MessageRole
    content: str | list[dict[str, Any]]


class LLMRequest(BaseModel):
    model: str
    messages: list[LLMMessage]
    system: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[ToolDefinition] | None = None


class LLMUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


# ── События стрима (унифицированные для всех провайдеров) ────────────────────

class StreamEventType(StrEnum):
    START = "start"
    DELTA = "delta"
    DONE = "done"
    ERROR = "error"
    # Эмитится use-case'ом (не адаптером): когда мы распарсили из стрима
    # обновлённый артефакт. Полезная нагрузка в `raw`: {"artifact_id", ...}.
    ARTIFACT = "artifact"
    # Адаптер запросил вызов инструмента (tool_use из Anthropic / function_call
    # из OpenAI). Полезная нагрузка в `raw`: {"id", "name", "input"}.
    # После исполнения use-case добавляет tool_result в историю и шлёт
    # модели новый запрос.
    TOOL_USE = "tool_use"
    # Use-case эмитит до/после выполнения инструмента — для UI.
    TOOL_RESULT = "tool_result"
    # Стрим оборвался из-за лимита итераций tool-use (не error, штатно).
    # Фронт покажет кнопку «продолжить».
    TRUNCATED = "truncated"


# ── Tools ─────────────────────────────────────────────────────────────────────

class ToolDefinition(BaseModel):
    """
    Описание инструмента, которое отправляется в LLM (Anthropic/OpenAI format).
    `input_schema` — JSON Schema параметров.
    """
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolUseRequest(BaseModel):
    """Модель попросила вызвать инструмент."""
    id: str                    # tool_use_id (нужен чтобы матчить результат)
    name: str
    input: dict[str, Any]


class ToolUseResult(BaseModel):
    """Результат вызова инструмента — отдаётся обратно в LLM."""
    tool_use_id: str
    content: str               # plain текст (или сериализованный JSON)
    is_error: bool = False


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
