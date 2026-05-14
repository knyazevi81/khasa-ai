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


class OllamaAdapter(AbstractLLMService):
    """
    Адаптер для локального Ollama. Никаких ключей — только base_url.
    Для Ollama credential.secret игнорируется (но может содержать что-то для
    обратной совместимости), важен credential.base_url.
    """

    provider_name = "ollama"
    DEFAULT_BASE = "http://localhost:11434"

    def __init__(self, timeout: float = 300.0) -> None:
        self._timeout = timeout

    async def stream(
        self,
        credential: LLMCredential,
        request: LLMRequest,
    ) -> AsyncIterator[StreamEvent]:
        base = credential.base_url or self.DEFAULT_BASE
        url = f"{base.rstrip('/')}/api/chat"

        messages: list[dict] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for m in request.messages:
            messages.append({"role": m.role.value, "content": m.content})

        body: dict = {
            "model": request.model,
            "messages": messages,
            "stream": True,
            "options": {},
        }
        if request.temperature is not None:
            body["options"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["options"]["num_predict"] = request.max_tokens

        usage = LLMUsage()
        yield StreamEvent(type=StreamEventType.START)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, json=body) as resp:
                    if resp.status_code != 200:
                        text = await resp.aread()
                        yield StreamEvent(
                            type=StreamEventType.ERROR,
                            error=f"ollama {resp.status_code}: {text.decode(errors='ignore')[:300]}",
                        )
                        return

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            evt = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        msg = evt.get("message") or {}
                        chunk = msg.get("content")
                        if chunk:
                            yield StreamEvent(
                                type=StreamEventType.DELTA,
                                text=chunk,
                            )

                        if evt.get("done"):
                            # Ollama возвращает eval_count / prompt_eval_count
                            usage.input_tokens = evt.get("prompt_eval_count", 0)
                            usage.output_tokens = evt.get("eval_count", 0)
                            break
        except (httpx.HTTPError, httpx.StreamError) as exc:
            yield StreamEvent(type=StreamEventType.ERROR, error=f"http: {exc}")
            return

        yield StreamEvent(type=StreamEventType.DONE, usage=usage)

    async def validate_credential(self, credential: LLMCredential) -> bool:
        base = credential.base_url or self.DEFAULT_BASE
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base.rstrip('/')}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self, credential: LLMCredential) -> list[str]:
        """
        Ollama: GET /api/tags возвращает список локально установленных
        моделей. Это «честный» список — то, что реально доступно.
        """
        base = credential.base_url or self.DEFAULT_BASE
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base.rstrip('/')}/api/tags")
                if resp.status_code != 200:
                    return []
                data = resp.json()
                models = data.get("models") or []
                return [m.get("name") for m in models if m.get("name")]
        except httpx.HTTPError:
            return []
