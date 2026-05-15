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

        # OpenAI принимает content либо как строку, либо как массив частей.
        # У нас в LLMMessage.content может быть list[dict] — это блоки в
        # Anthropic-формате. Для OpenAI конвертируем:
        #   text-блок → {"type": "text", "text": "..."} в content
        #   tool_use  → assistant message с tool_calls[]
        #   tool_result → отдельное message с role="tool"
        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})

        for m in request.messages:
            if m.role == MessageRole.SYSTEM:
                messages.append({"role": "system", "content": _stringify(m.content)})
                continue

            if isinstance(m.content, str):
                messages.append({"role": m.role.value, "content": m.content})
                continue

            # list-content — конвертируем в OpenAI-формат
            text_parts: list[str] = []
            tool_calls: list[dict] = []
            tool_results: list[dict] = []
            for block in m.content:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls.append({
                        "id": block.get("id"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input") or {}),
                        },
                    })
                elif btype == "tool_result":
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": _stringify(block.get("content", "")),
                    })

            if m.role == MessageRole.ASSISTANT:
                msg: dict = {"role": "assistant"}
                if text_parts:
                    msg["content"] = "\n".join(text_parts)
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                if "content" not in msg and not tool_calls:
                    msg["content"] = ""
                messages.append(msg)
            elif m.role == MessageRole.USER:
                # User-сообщение содержит либо текст, либо tool_result'ы
                # (после исполнения tools мы кладём их в user-message с
                # list-content). Если в одном куске и tool_result, и текст —
                # отдадим tool_result'ы отдельными сообщениями + основное.
                for tr in tool_results:
                    messages.append(tr)
                if text_parts:
                    messages.append({"role": "user", "content": "\n".join(text_parts)})

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
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]

        headers = {
            "Authorization": f"Bearer {credential.secret}",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        usage = LLMUsage()
        yield StreamEvent(type=StreamEventType.START)

        # Аккумулятор tool_call'ов: OpenAI стримит их по частям с index'ами
        tool_call_acc: dict[int, dict] = {}

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

                            # Аккумулируем tool_calls
                            for tc in delta.get("tool_calls") or []:
                                idx = tc.get("index", 0)
                                acc = tool_call_acc.setdefault(idx, {
                                    "id": None,
                                    "name": None,
                                    "arguments": "",
                                })
                                if tc.get("id"):
                                    acc["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    acc["name"] = fn["name"]
                                if fn.get("arguments"):
                                    acc["arguments"] += fn["arguments"]

                            finish = choices[0].get("finish_reason")
                            if finish == "tool_calls":
                                # Эмитим все собранные tool_use'ы
                                for idx in sorted(tool_call_acc.keys()):
                                    acc = tool_call_acc[idx]
                                    try:
                                        parsed_args = json.loads(acc["arguments"] or "{}")
                                    except json.JSONDecodeError:
                                        parsed_args = {}
                                    yield StreamEvent(
                                        type=StreamEventType.TOOL_USE,
                                        raw={
                                            "id": acc["id"],
                                            "name": acc["name"],
                                            "input": parsed_args,
                                        },
                                    )
                                tool_call_acc.clear()

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


def _stringify(x) -> str:
    """Превращает str/list/dict в строку для OpenAI content field."""
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        parts: list[str] = []
        for item in x:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(x)
