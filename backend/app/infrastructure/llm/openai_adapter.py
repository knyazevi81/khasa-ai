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


class OpenAIAdapter(AbstractLLMService):
    """
    Адаптер для OpenAI Chat Completions API.
    Работает и с OpenAI, и с любым OpenAI-совместимым endpoint
    (Together, OpenRouter, локальные обёртки) — нужно лишь base_url.
    """

    provider_name = "openai"
    DEFAULT_BASE = "https://api.openai.com"

    def __init__(self, timeout: float = 120.0) -> None:
        self._timeout = timeout

    async def stream(
        self,
        credential: LLMCredential,
        request: LLMRequest,
    ) -> AsyncIterator[StreamEvent]:
        base = credential.base_url or self.DEFAULT_BASE
        url = f"{base.rstrip('/')}/v1/chat/completions"

        # OpenAI хочет system как первое сообщение в массиве
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            if m.role == MessageRole.SYSTEM:
                # система уже добавлена выше; дополнительные system-сообщения
                # тоже пропустим внутрь — OpenAI разрешает несколько system
                messages.append({"role": "system", "content": m.content})
            else:
                messages.append({"role": m.role.value, "content": m.content})

        body: dict = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens

        headers = {
            "Authorization": f"Bearer {credential.secret}",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        usage = LLMUsage()
        yield StreamEvent(type=StreamEventType.START)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, headers=headers, json=body) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        yield StreamEvent(
                            type=StreamEventType.ERROR,
                            error=f"openai {resp.status_code}: {text.decode(errors='ignore')[:300]}",
                        )
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if not payload:
                            continue
                        if payload == "[DONE]":
                            break
                        try:
                            evt = json.loads(payload)
                        except json.JSONDecodeError:
                            continue

                        choices = evt.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta") or {}
                            text_chunk = delta.get("content")
                            if text_chunk:
                                yield StreamEvent(
                                    type=StreamEventType.DELTA,
                                    text=text_chunk,
                                )

                        u = evt.get("usage")
                        if u:
                            usage.input_tokens = u.get("prompt_tokens", usage.input_tokens)
                            usage.output_tokens = u.get("completion_tokens", usage.output_tokens)
        except (httpx.HTTPError, httpx.StreamError) as exc:
            yield StreamEvent(type=StreamEventType.ERROR, error=f"http: {exc}")
            return

        yield StreamEvent(type=StreamEventType.DONE, usage=usage)

    async def validate_credential(self, credential: LLMCredential) -> bool:
        base = credential.base_url or self.DEFAULT_BASE
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base.rstrip('/')}/v1/models",
                    headers={"Authorization": f"Bearer {credential.secret}"},
                )
                return resp.status_code != 401
        except httpx.HTTPError:
            return False

    async def list_models(self, credential: LLMCredential) -> list[str]:
        """
        Стандартный OpenAI-совместимый /v1/models. Фильтруем под чат-модели —
        выкидываем embeddings/audio/whisper/image.
        """
        base = credential.base_url or self.DEFAULT_BASE
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{base.rstrip('/')}/v1/models",
                    headers={"Authorization": f"Bearer {credential.secret}"},
                )
                if resp.status_code != 200:
                    return _FALLBACK_OPENAI
                data = resp.json()
                items = data.get("data") or []
                ids = [m.get("id") for m in items if m.get("id")]
                chat_like = [
                    m for m in ids
                    if any(p in m for p in ("gpt-", "o1", "o3", "o4", "chatgpt"))
                    and not any(p in m for p in (
                        "embed", "whisper", "audio", "image", "tts", "dall-e", "moderation",
                    ))
                ]
                chat_like.sort()
                return chat_like or _FALLBACK_OPENAI
        except httpx.HTTPError:
            return _FALLBACK_OPENAI


_FALLBACK_OPENAI = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]
