from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    pass


class MCPClient:
    """
    Обёртка над `mcp` Python SDK. Открывает сессию на сервер юзера и:
      • даёт список инструментов (`list_tools`);
      • вызывает инструмент (`call_tool`).

    Поддерживаются транспорты:
      • `http` / `sse` — URL, обычный HTTP+SSE сервер;
      • `stdio` — локальная команда (для MVP не рекомендуется на сервере,
        потому что spawn process'ов из backend-контейнера требует особых
        настроек; но реализация поддерживает).

    Дизайн: одна сессия на один вызов — короткие коннекты вместо постоянных.
    Так проще, и MCP-сервера обычно с этим ок (особенно http/sse).
    """

    def __init__(self, transport: str, url: str | None, command: dict | None) -> None:
        self.transport = transport
        self.url = url
        self.command = command or {}

    @asynccontextmanager
    async def _session(self):
        # SDK импортируем лениво — если пакет не установлен, MCP-фича просто
        # будет недоступна, а остальное приложение запустится.
        try:
            from mcp import ClientSession
        except ImportError as exc:
            raise MCPClientError(
                "MCP SDK не установлен. Установите `mcp[cli]` в backend."
            ) from exc

        if self.transport in ("http", "sse"):
            try:
                from mcp.client.sse import sse_client
            except ImportError as exc:
                raise MCPClientError(f"mcp.client.sse недоступен: {exc}") from exc
            if not self.url:
                raise MCPClientError("URL обязателен для http/sse транспорта")
            async with sse_client(self.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
            return

        if self.transport == "stdio":
            try:
                from mcp import StdioServerParameters
                from mcp.client.stdio import stdio_client
            except ImportError as exc:
                raise MCPClientError(f"mcp.client.stdio недоступен: {exc}") from exc
            cmd = self.command.get("command") or "/bin/echo"
            args = self.command.get("args") or []
            env = self.command.get("env") or None
            params = StdioServerParameters(command=cmd, args=args, env=env)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
            return

        raise MCPClientError(f"Неизвестный транспорт: {self.transport}")

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self._session() as session:
            resp = await session.list_tools()
            out: list[dict] = []
            for t in resp.tools:
                out.append({
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema or {"type": "object"},
                })
            return out

    async def call_tool(self, name: str, arguments: dict) -> str:
        async with self._session() as session:
            resp = await session.call_tool(name, arguments=arguments)
            # resp.content — список TextContent / ImageContent блоков
            parts: list[str] = []
            for block in resp.content:
                if hasattr(block, "text") and block.text:
                    parts.append(block.text)
                elif hasattr(block, "data"):
                    parts.append(f"[binary {getattr(block, 'mimeType', '?')}]")
            if resp.isError:
                return "ERROR: " + "\n".join(parts)
            return "\n".join(parts) or "(empty)"
