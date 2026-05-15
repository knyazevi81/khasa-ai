from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class SandboxResponse(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    user_id: uuid.UUID
    container_id: str | None
    container_name: str
    image: str
    status: str
    workspace_path: str
    last_used_at: str | None = None
    error: str | None = None


class ExecRequest(BaseModel):
    command: str = Field(min_length=1, max_length=10_000)
    timeout: int = Field(default=60, ge=1, le=300)


class ExecResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class FileEntry(BaseModel):
    path: str
    is_dir: bool
    size: int
    modified_at: float


class FileListResponse(BaseModel):
    files: list[FileEntry]
    workspace: str


class AdminSandboxRow(BaseModel):
    id: str
    chat_id: str
    user_id: str
    container_id: str | None
    container_name: str
    image: str
    status_db: str
    status_live: str | None
    workspace_path: str
    last_used_at: str | None
    error: str | None


class AdminSandboxListResponse(BaseModel):
    sandboxes: list[AdminSandboxRow]
    total: int
