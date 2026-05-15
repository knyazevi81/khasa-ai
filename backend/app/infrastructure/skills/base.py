from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.domain.models.llm import ToolDefinition
from app.infrastructure.sandbox.docker_manager import DockerSandboxManager


@dataclass
class SkillContext:
    """
    Контекст исполнения скилла — передаётся внутрь `execute()`.
    Содержит ссылку на песочницу чата и идентификаторы для аудит-лога.
    """
    chat_id: uuid.UUID
    user_id: uuid.UUID
    container_id: str
    sandbox: DockerSandboxManager


class AbstractSkill(ABC):
    """Базовый скилл-инструмент. Определяет название, схему и логику."""

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    @abstractmethod
    async def execute(
        self, args: dict[str, Any], ctx: SkillContext
    ) -> str:
        """
        Возвращает строку — то, что мы покажем LLM как результат.
        Может бросить исключение — оно будет завёрнуто в tool_result is_error.
        """
        ...


class SkillRegistry:
    """Реестр доступных скиллов. Регистрация — singleton на процесс."""

    def __init__(self) -> None:
        self._skills: dict[str, AbstractSkill] = {}

    def register(self, skill: AbstractSkill) -> None:
        if not skill.name:
            raise ValueError("skill.name required")
        self._skills[skill.name] = skill

    def get(self, name: str) -> AbstractSkill | None:
        return self._skills.get(name)

    def all(self) -> list[AbstractSkill]:
        return list(self._skills.values())

    def definitions(self) -> list[ToolDefinition]:
        return [s.definition() for s in self._skills.values()]
