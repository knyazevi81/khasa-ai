from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class MCPServerResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    transport: str
    url: str | None
    command: dict | None
    config: dict | None
    is_enabled: bool
    tools_cache: dict | None

    model_config = {"from_attributes": True}


class MCPServerListResponse(BaseModel):
    servers: list[MCPServerResponse]
    total: int


class MCPServerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    transport: str = Field(pattern="^(sse|http|stdio)$")
    url: str | None = Field(default=None, max_length=500)
    command: dict | None = None
    config: dict | None = None


class MCPServerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    transport: str | None = Field(default=None, pattern="^(sse|http|stdio)$")
    url: str | None = Field(default=None, max_length=500)
    command: dict | None = None
    config: dict | None = None
    is_enabled: bool | None = None


class MCPToolInfo(BaseModel):
    name: str
    description: str
    input_schema: dict


class MCPValidateResponse(BaseModel):
    tools: list[MCPToolInfo]
