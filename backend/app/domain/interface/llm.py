from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.domain.models.llm import LLMCredential, LLMRequest, StreamEvent


class AbstractLLMService(ABC):
    """
    Порт для общения с LLM-провайдером.

    Все адаптеры (Anthropic / OpenAI / Ollama) реализуют один и тот же стрим
    унифицированных StreamEvent'ов. Это позволяет верхнему слою (use_cases)
    оставаться полностью провайдер-агностичным.
    """

    provider_name: str

    @abstractmethod
    async def stream(
        self,
        credential: LLMCredential,
        request: LLMRequest,
    ) -> AsyncIterator[StreamEvent]:
        """
        Открывает соединение с провайдером и асинхронно отдаёт события.
        Должна корректно отрабатывать отмену (CancelledError).
        """
        ...

    @abstractmethod
    async def validate_credential(self, credential: LLMCredential) -> bool:
        """Дешёвая проверка, что ключ/endpoint вообще работает."""
        ...


class AbstractLLMRouter(ABC):
    """Маршрутизатор: по `LLMProvider` отдаёт нужный адаптер."""

    @abstractmethod
    def get(self, provider: str) -> AbstractLLMService: ...
