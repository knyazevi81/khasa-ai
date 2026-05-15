from __future__ import annotations

import logging
import uuid

from app.domain.exceptions.base import AppException
from app.infrastructure.database.orm.models import MCPServers
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.mcp.client import MCPClient, MCPClientError

logger = logging.getLogger(__name__)


class MCPServerNotFoundError(AppException):
    code = 404
    message = "MCP-сервер не найден"


class MCPValidationError(AppException):
    code = 400
    message = "MCP-сервер не отвечает или его tools не удалось получить"


class MCPService:
    """
    CRUD над MCP-серверами юзера + сборка их инструментов для агента.

    При validate подключается к серверу, тянет список tools и кэширует
    его в `tools_cache` (чтобы при каждом вызове чата не дёргать сервер
    повторно — список меняется редко).
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def list_for_user(self, user_id: uuid.UUID) -> list[MCPServers]:
        return await self.uow.mcp_servers.find_for_user(user_id)

    async def get_for_user(
        self, server_id: uuid.UUID, user_id: uuid.UUID
    ) -> MCPServers:
        row = await self.uow.mcp_servers.get_by_id(server_id)
        if not row or row.user_id != user_id:
            raise MCPServerNotFoundError()
        return row

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        description: str | None,
        transport: str,
        url: str | None,
        command: dict | None,
        config: dict | None,
    ) -> MCPServers:
        server_id = uuid.uuid4()
        await self.uow.mcp_servers.add(
            id=server_id,
            user_id=user_id,
            name=name,
            description=description,
            transport=transport,
            url=url,
            command=command,
            config=config,
            is_enabled=True,
            tools_cache=None,
        )
        return await self.get_for_user(server_id, user_id)

    async def update(
        self,
        *,
        server_id: uuid.UUID,
        user_id: uuid.UUID,
        **fields,
    ) -> MCPServers:
        await self.get_for_user(server_id, user_id)
        await self.uow.mcp_servers.update_fields(server_id, **fields)
        return await self.get_for_user(server_id, user_id)

    async def delete(self, server_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.uow.mcp_servers.delete_for_user(server_id, user_id)

    async def validate_and_refresh(
        self, server_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[dict]:
        """
        Подключиться к серверу, получить tools, сохранить кэш. Возвращает
        список tools. На ошибке коннекта — бросает MCPValidationError.
        """
        row = await self.get_for_user(server_id, user_id)
        client = MCPClient(
            transport=row.transport, url=row.url, command=row.command
        )
        try:
            tools = await client.list_tools()
        except MCPClientError as exc:
            raise MCPValidationError(str(exc)) from exc
        except Exception as exc:
            logger.warning("mcp validate failed: %s", exc)
            raise MCPValidationError(f"{type(exc).__name__}: {exc}") from exc

        await self.uow.mcp_servers.update_fields(
            server_id,
            tools_cache={"tools": tools},
        )
        await self.uow.session.commit()
        return tools

    async def collect_tools_for_user(
        self, user_id: uuid.UUID
    ) -> list[tuple[MCPServers, list[dict]]]:
        """
        Возвращает список (server, tools[]) для всех включённых серверов юзера.
        Использует tools_cache (без сетевых вызовов). Если кэш пуст — пропускает.
        """
        servers = await self.uow.mcp_servers.find_for_user(user_id)
        out: list[tuple[MCPServers, list[dict]]] = []
        for s in servers:
            if not s.is_enabled:
                continue
            cache = s.tools_cache or {}
            tools = cache.get("tools") or []
            if tools:
                out.append((s, tools))
        return out

    async def call_tool(
        self,
        *,
        server: MCPServers,
        tool_name: str,
        arguments: dict,
    ) -> str:
        client = MCPClient(
            transport=server.transport, url=server.url, command=server.command
        )
        try:
            return await client.call_tool(tool_name, arguments)
        except Exception as exc:
            return f"ERROR: MCP call failed: {exc}"
