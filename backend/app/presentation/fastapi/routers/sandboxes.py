from __future__ import annotations

import io
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.application.use_cases.sandboxes import SandboxService
from app.domain.exceptions.base import ForbiddenError
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import (
    get_current_user,
    get_sandbox_service,
)
from app.presentation.fastapi.schemas.sandboxes import (
    AdminSandboxListResponse,
    AdminSandboxRow,
    ExecRequest,
    ExecResponse,
    FileEntry,
    FileListResponse,
    SandboxResponse,
)
from app.presentation.fastapi.schemas.schemas import MessageResponse


def _to_resp(sb) -> SandboxResponse:
    return SandboxResponse(
        id=sb.id,
        chat_id=sb.chat_id,
        user_id=sb.user_id,
        container_id=sb.container_id,
        container_name=sb.container_name,
        image=sb.image,
        status=sb.status,
        workspace_path=sb.workspace_path,
        last_used_at=sb.last_used_at.isoformat() if sb.last_used_at else None,
        error=sb.error,
    )


# ── per-chat endpoints ──────────────────────────────────────────────────────

chat_router = APIRouter(prefix="/chats", tags=["sandboxes"])


@chat_router.get("/{chat_id}/sandbox", response_model=SandboxResponse)
async def get_or_create_sandbox(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
) -> SandboxResponse:
    sb = await service.get_or_create_for_chat(chat_id, current_user.id)
    return _to_resp(sb)


@chat_router.delete("/{chat_id}/sandbox", response_model=MessageResponse)
async def remove_sandbox(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
) -> MessageResponse:
    sb = await service.uow.sandboxes.get_for_chat(chat_id)
    if not sb:
        return MessageResponse(message="Песочница не была создана")
    await service.remove(
        sb.id,
        {"id": current_user.id, "is_superuser": current_user.is_superuser},
    )
    return MessageResponse(message="Удалено")


@chat_router.get("/{chat_id}/files/", response_model=FileListResponse)
async def list_files(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
    subdir: str = "",
) -> FileListResponse:
    chat = await service.uow.chats.get_for_user(chat_id, current_user.id)
    if not chat:
        raise HTTPException(404, "chat not found")
    files = service.list_files(chat_id, subdir)
    workspace = service.manager.workspace_for(chat_id)
    return FileListResponse(
        files=[FileEntry(**f) for f in files],
        workspace=workspace,
    )


@chat_router.get("/{chat_id}/files/download")
async def download_file(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
    path: str,
):
    chat = await service.uow.chats.get_for_user(chat_id, current_user.id)
    if not chat:
        raise HTTPException(404, "chat not found")
    full = service.get_host_file_path(chat_id, path)
    if not full:
        raise HTTPException(404, "file not found")
    # FileResponse(filename=...) кладёт имя в Content-Disposition как latin-1,
    # что падает на unicode (кириллица, emoji). Делаем вручную с RFC 5987.
    fname = os.path.basename(full)
    return FileResponse(full, headers=_unicode_disposition(fname))


@chat_router.get("/{chat_id}/files.zip")
async def download_workspace_zip(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
):
    chat = await service.uow.chats.get_for_user(chat_id, current_user.id)
    if not chat:
        raise HTTPException(404, "chat not found")
    archive = service.zip_workspace(chat_id)
    fname = f"workspace-{str(chat_id)[:8]}.zip"
    return FileResponse(archive, headers=_unicode_disposition(fname))


def _unicode_disposition(filename: str) -> dict[str, str]:
    """RFC 6266 + 5987: filename + filename* для unicode-имён."""
    from urllib.parse import quote
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
    encoded = quote(filename, safe="")
    return {
        "Content-Disposition": (
            f'attachment; filename="{ascii_fallback}"; '
            f"filename*=UTF-8''{encoded}"
        )
    }


# ── admin endpoints ─────────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/admin/sandboxes", tags=["admin-sandboxes"])


def _require_admin(user: User) -> None:
    if not user.is_superuser:
        raise ForbiddenError()


@admin_router.get("/", response_model=AdminSandboxListResponse)
async def admin_list(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
) -> AdminSandboxListResponse:
    _require_admin(current_user)
    rows = await service.admin_list_all()
    return AdminSandboxListResponse(
        sandboxes=[AdminSandboxRow(**r) for r in rows],
        total=len(rows),
    )


@admin_router.post("/{sandbox_id}/exec", response_model=ExecResponse)
async def admin_exec(
    sandbox_id: uuid.UUID,
    body: ExecRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
) -> ExecResponse:
    _require_admin(current_user)
    sb = await service.uow.sandboxes.get_by_id(sandbox_id)
    if not sb:
        raise HTTPException(404, "sandbox not found")
    if not sb.container_id:
        raise HTTPException(400, "container not running")
    result = await service.manager.exec(
        sb.container_id, body.command, timeout=body.timeout
    )
    return ExecResponse(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        timed_out=result.timed_out,
    )


@admin_router.delete("/{sandbox_id}", response_model=MessageResponse)
async def admin_remove(
    sandbox_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SandboxService, Depends(get_sandbox_service)],
) -> MessageResponse:
    _require_admin(current_user)
    await service.remove(
        sandbox_id,
        {"id": current_user.id, "is_superuser": True},
    )
    return MessageResponse(message="Удалено")
