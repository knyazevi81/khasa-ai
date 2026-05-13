from __future__ import annotations

from app.domain.exceptions.base import AppException
from app.domain.interface.llm import AbstractLLMRouter, AbstractLLMService
from app.domain.models.llm import LLMProvider
from app.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from app.infrastructure.llm.ollama_adapter import OllamaAdapter
from app.infrastructure.llm.openai_adapter import OpenAIAdapter


class UnknownProviderError(AppException):
    code = 400
    message = "Неизвестный LLM-провайдер"


class LLMRouter(AbstractLLMRouter):
    """Простой dict-based маршрутизатор. Адаптеры — singleton'ы, без состояния."""

    def __init__(self) -> None:
        self._adapters: dict[str, AbstractLLMService] = {
            LLMProvider.ANTHROPIC.value: AnthropicAdapter(),
            LLMProvider.OPENAI.value: OpenAIAdapter(),
            LLMProvider.OLLAMA.value: OllamaAdapter(),
        }

    def get(self, provider: str) -> AbstractLLMService:
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise UnknownProviderError(f"Провайдер '{provider}' не поддерживается")
        return adapter
