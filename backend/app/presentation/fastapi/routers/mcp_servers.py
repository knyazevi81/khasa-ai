from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.mcp_servers import MCPService
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import (
    get_current_user,
    get_mcp_service,
)
from app.presentation.fastapi.schemas.mcp_servers import (
    MCPServerCreateRequest,
    MCPServerListResponse,
    MCPServerResponse,
    MCPServerUpdateRequest,
    MCPToolInfo,
    MCPValidateResponse,
)
from app.presentation.fastapi.schemas.schemas import MessageResponse

router = APIRouter(prefix="/mcp-servers", tags=["mcp"])


@router.get("/", response_model=MCPServerListResponse)
async def list_servers(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPService, Depends(get_mcp_service)],
) -> MCPServerListResponse:
    rows = await service.list_for_user(current_user.id)
    return MCPServerListResponse(
        servers=[MCPServerResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("/", response_model=MCPServerResponse, status_code=201)
async def create_server(
    body: MCPServerCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPService, Depends(get_mcp_service)],
) -> MCPServerResponse:
    row = await service.create(
        user_id=current_user.id,
        name=body.name,
        description=body.description,
        transport=body.transport,
        url=body.url,
        command=body.command,
        config=body.config,
    )
    return MCPServerResponse.model_validate(row)


@router.patch("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: uuid.UUID,
    body: MCPServerUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPService, Depends(get_mcp_service)],
) -> MCPServerResponse:
    row = await service.update(
        server_id=server_id,
        user_id=current_user.id,
        **body.model_dump(exclude_unset=True),
    )
    return MCPServerResponse.model_validate(row)


@router.delete("/{server_id}", response_model=MessageResponse)
async def delete_server(
    server_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPService, Depends(get_mcp_service)],
) -> MessageResponse:
    await service.delete(server_id, current_user.id)
    return MessageResponse(message="Удалено")


@router.post("/{server_id}/validate", response_model=MCPValidateResponse)
async def validate_server(
    server_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[MCPService, Depends(get_mcp_service)],
) -> MCPValidateResponse:
    tools = await service.validate_and_refresh(server_id, current_user.id)
    return MCPValidateResponse(
        tools=[MCPToolInfo(**t) for t in tools],
    )
