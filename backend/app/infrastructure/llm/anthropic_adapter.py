from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.domain.interface.llm import AbstractLLMService
from app.domain.models.llm import (
    LLMCredential,
    LLMRequest,
    LLMUsage,
    MessageRole,
    StreamEvent,
    StreamEventType,
)

logger = logging.getLogger(__name__)


class AnthropicAdapter(AbstractLLMService):
    """
    Адаптер для Anthropic Messages API.
    Использует SSE-стрим (`stream: true`) и нормализует события в StreamEvent.
    """

    provider_name = "anthropic"
    DEFAULT_BASE = "https://api.anthropic.com"
    API_VERSION = "2023-06-01"

    def __init__(self, timeout: float = 120.0) -> None:
        self._timeout = timeout

    async def stream(
        self,
        credential: LLMCredential,
        request: LLMRequest,
    ) -> AsyncIterator[StreamEvent]:
        base = credential.base_url or self.DEFAULT_BASE
        url = f"{base.rstrip('/')}/v1/messages"

        # Anthropic принимает контент как string или list[block]. У нас domain
        # LLMMessage.content уже умеет быть list — передаём как есть.
        messages: list[dict] = []
        for m in request.messages:
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT):
                messages.append({"role": m.role.value, "content": m.content})

        body: dict = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "stream": True,
        }
        if request.system:
            body["system"] = request.system
        if request.temperature is not None:
            body["temperature"] = request.temperature
        # Tool use: пробрасываем список инструментов и схему
        if request.tools:
            body["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in request.tools
            ]

        headers = {
            "x-api-key": credential.secret,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        usage = LLMUsage()
        yield StreamEvent(type=StreamEventType.START)

        # Состояние парсинга стрима. У Anthropic несколько content_block-ов,
        # каждый со своим индексом. Нам важны text и tool_use.
        current_blocks: dict[int, dict] = {}  # index -> {type, ...}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        yield StreamEvent(
                            type=StreamEventType.ERROR,
                            error=f"anthropic {resp.status_code}: {text.decode(errors='ignore')[:300]}",
                        )
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if not payload or payload == "[DONE]":
                            continue
                        try:
                            evt = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        et = evt.get("type")

                        if et == "content_block_start":
                            idx = evt.get("index", 0)
                            block = evt.get("content_block") or {}
                            current_blocks[idx] = {
                                "type": block.get("type"),
                                "id": block.get("id"),
                                "name": block.get("name"),
                                "input_buffer": "",
                            }

                        elif et == "content_block_delta":
                            idx = evt.get("index", 0)
                            delta = evt.get("delta", {})
                            block = current_blocks.get(idx, {})
                            dt = delta.get("type")
                            if dt == "text_delta":
                                yield StreamEvent(
                                    type=StreamEventType.DELTA,
                                    text=delta.get("text", ""),
                                )
                            elif dt == "input_json_delta":
                                # Anthropic стримит JSON параметров tool_use по частям
                                block["input_buffer"] = (
                                    block.get("input_buffer", "")
                                    + delta.get("partial_json", "")
                                )

                        elif et == "content_block_stop":
                            idx = evt.get("index", 0)
                            block = current_blocks.get(idx)
                            if block and block.get("type") == "tool_use":
                                # Соберём полный input и эмитим TOOL_USE
                                try:
                                    parsed_input = json.loads(
                                        block.get("input_buffer") or "{}"
                                    )
                                except json.JSONDecodeError:
                                    parsed_input = {}
                                yield StreamEvent(
                                    type=StreamEventType.TOOL_USE,
                                    raw={
                                        "id": block.get("id"),
                                        "name": block.get("name"),
                                        "input": parsed_input,
                                    },
                                )

                        elif et == "message_delta":
                            u = evt.get("usage", {})
                            usage.output_tokens += u.get("output_tokens", 0)
                        elif et == "message_start":
                            u = evt.get("message", {}).get("usage", {})
                            usage.input_tokens = u.get("input_tokens", 0)
                            usage.output_tokens = u.get("output_tokens", 0)
                        elif et == "error":
                            yield StreamEvent(
                                type=StreamEventType.ERROR,
                                error=str(evt.get("error")),
                            )
                            return
        except (httpx.HTTPError, httpx.StreamError) as exc:
            yield StreamEvent(type=StreamEventType.ERROR, error=f"http: {exc}")
            return

        yield StreamEvent(type=StreamEventType.DONE, usage=usage)

    async def validate_credential(self, credential: LLMCredential) -> bool:
        base = credential.base_url or self.DEFAULT_BASE
        # Самый дешёвый запрос: попытка отправить 1-токенное сообщение
        # на дешёвой модели. Если ключ невалиден — вернётся 401.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{base.rstrip('/')}/v1/messages",
                    headers={
                        "x-api-key": credential.secret,
                        "anthropic-version": self.API_VERSION,
                        "content-type": "application/json",
                    },
                    json={
                        "model": credential.default_model or "claude-haiku-4-5",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                )
                # 200/400 = ключ ок, 401 = плохой ключ
                return resp.status_code != 401
        except httpx.HTTPError:
            return False

    async def list_models(self, credential: LLMCredential) -> list[str]:
        """
        Anthropic поддерживает GET /v1/models (с пагинацией). Запрашиваем
        первую страницу, остальные нам не нужны для UI-селектора.
        """
        base = credential.base_url or self.DEFAULT_BASE
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base.rstrip('/')}/v1/models?limit=100",
                    headers={
                        "x-api-key": credential.secret,
                        "anthropic-version": self.API_VERSION,
                    },
                )
                if resp.status_code != 200:
                    return _FALLBACK_ANTHROPIC
                data = resp.json()
                items = data.get("data") or []
                return [m.get("id") for m in items if m.get("id")] or _FALLBACK_ANTHROPIC
        except httpx.HTTPError:
            return _FALLBACK_ANTHROPIC


# Fallback-набор моделей если /v1/models недоступен (старые ключи, прокси)
_FALLBACK_ANTHROPIC = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
]
