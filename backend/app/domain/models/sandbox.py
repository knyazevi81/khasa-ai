from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class SandboxStatus(StrEnum):
    """
    Жизненный цикл контейнера-песочницы.

    Поток: CREATED → RUNNING → STOPPED → REMOVED.
    FAILED — терминальное состояние с ошибкой Docker.
    """
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    REMOVED = "removed"
    FAILED = "failed"


class Sandbox(BaseModel):
    """
    Контейнер-песочница, привязанный к чату.
    Файлы юзера живут в bind-mount на хосте по пути
    `<host_workspace_root>/<chat_id>/`, что переживает рестарты контейнера.
    """
    id: uuid.UUID
    chat_id: uuid.UUID
    user_id: uuid.UUID
    container_id: str | None              # docker container id (64 hex)
    container_name: str                   # human-readable name
    image: str
    status: str                           # SandboxStatus
    workspace_path: str                   # путь на хосте, где лежат файлы
    last_used_at: datetime | None = None
    error: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
