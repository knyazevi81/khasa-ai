from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from app.domain.exceptions.base import AppException, ForbiddenError
from app.domain.models.sandbox import Sandbox, SandboxStatus
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.sandbox.docker_manager import (
    DockerSandboxManager,
    ExecResult,
    SandboxError,
)

logger = logging.getLogger(__name__)


class SandboxNotFoundError(AppException):
    code = 404
    message = "Песочница не найдена"


class SandboxService:
    """
    Управление песочницами чатов.

    Поднимает контейнер при первом обращении, переиспользует существующий
    при последующих. Файлы юзера переживают рестарты благодаря bind-mount
    на хосте.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        manager: DockerSandboxManager,
    ) -> None:
        self.uow = uow
        self.manager = manager

    async def get_or_create_for_chat(
        self, chat_id: uuid.UUID, user_id: uuid.UUID
    ) -> Sandbox:
        """
        Гарантирует что у чата есть запущенный sandbox-контейнер.
        Возвращает actual Sandbox с обновлённым container_id и status=running.
        """
        # Проверим что чат принадлежит юзеру
        chat = await self.uow.chats.get_for_user(chat_id, user_id)
        if not chat:
            raise SandboxNotFoundError("Чат не найден")

        existing = await self.uow.sandboxes.get_for_chat(chat_id)

        if existing is None:
            # Создаём запись + запускаем контейнер
            sandbox_id = uuid.uuid4()
            workspace = self.manager.workspace_for(chat_id)
            container_name = f"khasa-sandbox-{str(chat_id)[:12]}"
            await self.uow.sandboxes.add(
                id=sandbox_id,
                chat_id=chat_id,
                user_id=user_id,
                container_id=None,
                container_name=container_name,
                image=self.manager._image,
                status=SandboxStatus.CREATED.value,
                workspace_path=workspace,
                last_used_at=datetime.now(timezone.utc),
            )
            await self.uow.session.commit()

        sandbox = await self.uow.sandboxes.get_for_chat(chat_id)
        assert sandbox is not None

        # Поднимем (или пересоздадим) контейнер
        try:
            container_id, _ = await self.manager.ensure_running(
                chat_id=chat_id,
                existing_container_id=sandbox.container_id,
            )
        except SandboxError as exc:
            await self.uow.sandboxes.update_fields(
                sandbox.id,
                status=SandboxStatus.FAILED.value,
                error=str(exc),
            )
            await self.uow.session.commit()
            raise

        await self.uow.sandboxes.update_fields(
            sandbox.id,
            container_id=container_id,
            status=SandboxStatus.RUNNING.value,
            last_used_at=datetime.now(timezone.utc),
            error=None,
        )
        await self.uow.session.commit()

        return await self.uow.sandboxes.get_for_chat(chat_id)  # type: ignore

    async def exec_in_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        command: str,
        timeout: int = 60,
    ) -> ExecResult:
        """Прямой exec в контейнер чата (используется админом и tools)."""
        sandbox = await self.get_or_create_for_chat(chat_id, user_id)
        assert sandbox.container_id is not None
        return await self.manager.exec(
            sandbox.container_id, command, timeout=timeout
        )

    async def stop(self, sandbox_id: uuid.UUID, requester: dict) -> None:
        sb = await self.uow.sandboxes.get_by_id(sandbox_id)
        if not sb:
            raise SandboxNotFoundError()
        # Юзер может тушить только свои; админ — любые
        if not requester.get("is_superuser") and sb.user_id != requester["id"]:
            raise ForbiddenError()
        if sb.container_id:
            await self.manager.stop(sb.container_id)
        await self.uow.sandboxes.update_fields(
            sandbox_id, status=SandboxStatus.STOPPED.value
        )
        await self.uow.session.commit()

    async def remove(self, sandbox_id: uuid.UUID, requester: dict) -> None:
        sb = await self.uow.sandboxes.get_by_id(sandbox_id)
        if not sb:
            raise SandboxNotFoundError()
        if not requester.get("is_superuser") and sb.user_id != requester["id"]:
            raise ForbiddenError()
        if sb.container_id:
            await self.manager.remove(sb.container_id)
        await self.uow.sandboxes.remove(sandbox_id)
        await self.uow.session.commit()

    async def admin_list_all(self) -> list[dict]:
        """
        Список ВСЕХ песочниц для админ-страницы.
        Подмешивает живой статус контейнера из Docker — потому что в БД
        может быть status=running, а контейнер уже умер сам.
        """
        rows = await self.uow.sandboxes.all_with_users()
        live = {c["container_id"]: c for c in await self.manager.list_containers()}
        out: list[dict] = []
        for sb in rows:
            live_info = live.get(sb.container_id) if sb.container_id else None
            out.append({
                "id": str(sb.id),
                "chat_id": str(sb.chat_id),
                "user_id": str(sb.user_id),
                "container_id": sb.container_id,
                "container_name": sb.container_name,
                "image": sb.image,
                "status_db": sb.status,
                "status_live": (live_info or {}).get("status"),
                "workspace_path": sb.workspace_path,
                "last_used_at": sb.last_used_at.isoformat() if sb.last_used_at else None,
                "error": sb.error,
            })
        return out

    # ── workspace files ──────────────────────────────────────────────────────

    def list_files(self, chat_id: uuid.UUID, subdir: str = "") -> list[dict]:
        """Список файлов в workspace чата (на хосте, не в контейнере)."""
        root = self.manager.workspace_for(chat_id)
        target = os.path.normpath(os.path.join(root, subdir.lstrip("/")))
        if not target.startswith(root):
            return []  # escape attempt
        if not os.path.isdir(target):
            return []
        out: list[dict] = []
        for entry in sorted(os.listdir(target)):
            full = os.path.join(target, entry)
            rel = os.path.relpath(full, root)
            stat = os.stat(full)
            out.append({
                "path": rel,
                "is_dir": os.path.isdir(full),
                "size": stat.st_size if not os.path.isdir(full) else 0,
                "modified_at": stat.st_mtime,
            })
        return out

    def get_host_file_path(self, chat_id: uuid.UUID, rel_path: str) -> str | None:
        """Безопасно резолвит путь в workspace для скачивания."""
        root = self.manager.workspace_for(chat_id)
        target = os.path.normpath(os.path.join(root, rel_path.lstrip("/")))
        if not target.startswith(root):
            return None
        if not os.path.isfile(target):
            return None
        return target

    def zip_workspace(self, chat_id: uuid.UUID) -> str:
        """Запаковать весь workspace чата в zip и вернуть путь к архиву."""
        import shutil
        import tempfile
        root = self.manager.workspace_for(chat_id)
        tmp = tempfile.NamedTemporaryFile(
            prefix=f"khasa-{str(chat_id)[:8]}-",
            suffix=".zip",
            delete=False,
        )
        tmp.close()
        # shutil.make_archive добавляет .zip — уберём суффикс
        base = tmp.name[:-4]
        os.unlink(tmp.name)
        archive_path = shutil.make_archive(base, "zip", root_dir=root)
        return archive_path
