from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ArtifactKind(StrEnum):
    """
    Что мы умеем рендерить как «артефакт».
    Текст и код — обычные plain/markdown блоки с подсветкой; html/svg/mermaid
    рендерятся в iframe-песочнице или соответствующим рендерером.
    """
    MARKDOWN = "markdown"
    CODE = "code"
    HTML = "html"
    SVG = "svg"
    MERMAID = "mermaid"
    JSON = "json"


class Artifact(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    # Стабильный идентификатор внутри чата ("project-plan", "auth-snippet")
    # — позволяет LLM ссылаться на тот же артефакт между сообщениями и
    # обновлять его, а не создавать новый.
    slug: str
    kind: str                         # ArtifactKind
    title: str
    language: str | None = None       # для code: python, ts, ...
    current_version_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArtifactVersion(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    version_no: int
    content: str
    # Какое сообщение ассистента эту версию создало
    message_id: uuid.UUID
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
