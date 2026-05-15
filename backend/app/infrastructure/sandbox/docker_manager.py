from __future__ import annotations

import asyncio
import logging
import os
import shlex
import uuid
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import APIError, ImageNotFound, NotFound

from app.domain.exceptions.base import AppException

logger = logging.getLogger(__name__)


class SandboxError(AppException):
    code = 500
    message = "Ошибка песочницы"


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class DockerSandboxManager:
    """
    Управление контейнерами-песочницами через Docker Engine API.

    На бэкенде монтируется `/var/run/docker.sock` (или указан DOCKER_HOST для
    DinD/remote). Контейнеры стартуют от непривилегированного юзера, без сети
    наружу (но изнутри контейнера можно curl-ить allowlisted-хосты через
    отдельную сеть `khasa_sandbox_net` — для MVP это просто bridge).

    Workspace: `<host_workspace_root>/<chat_id>/` на хосте монтируется в
    `/workspace` внутри контейнера. Файлы переживают рестарты.

    ВАЖНО: блокирующие вызовы docker-py обёрнуты в `asyncio.to_thread` —
    docker-py синхронный, не имеет async API.
    """

    def __init__(
        self,
        *,
        image: str = "khasa-sandbox:latest",
        host_workspace_root: str = "/var/khasa/workspaces",
        container_workspace: str = "/workspace",
        network: str = "khasa_sandbox_net",
        cpu_quota: int = 50_000,      # 50% одного CPU
        mem_limit: str = "1g",
        exec_timeout_seconds: int = 60,
        host_workspace_root_external: str | None = None,
    ) -> None:
        self._image = image
        # Путь к workspace ВНУТРИ backend-контейнера (для нашего os.makedirs/
        # os.open и т.д.). Сюда смонтирован named volume / bind-mount.
        self._host_workspace_root = host_workspace_root
        # Путь, который backend передаёт Docker daemon'у при создании
        # sandbox-контейнера. Демон видит файловую систему ХОСТА, не наш
        # backend-контейнер. Поэтому если мы работаем через docker.sock,
        # backend должен знать "как этот путь выглядит снаружи".
        #
        # Для compose с named volume `khasa_workspaces` это
        # `/var/lib/docker/volumes/khasa_workspaces/_data` (на linux-хосте).
        # Если переменная не задана — fallback на host_workspace_root (это
        # работает когда backend запущен на самом хосте без контейнеризации).
        self._host_workspace_root_external = (
            host_workspace_root_external or host_workspace_root
        )
        self._container_workspace = container_workspace
        self._network = network
        self._cpu_quota = cpu_quota
        self._mem_limit = mem_limit
        self._exec_timeout = exec_timeout_seconds
        self._client: docker.DockerClient | None = None

    # ── client lifecycle ─────────────────────────────────────────────────────

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            # docker.from_env читает DOCKER_HOST из окружения, иначе использует
            # unix:///var/run/docker.sock
            self._client = docker.from_env()
        return self._client

    # ── workspace ────────────────────────────────────────────────────────────

    def workspace_for(self, chat_id: uuid.UUID) -> str:
        """
        Путь на хосте к workspace конкретного чата.

        Создаёт директорию если её нет и выставляет владельца uid/gid 10001:10001
        — это юзер `sandbox` внутри контейнера. Без этого `bash` от 10001
        не сможет ничего писать в bind-mount, который изначально создаётся
        от root (потому что backend в dev-контейнере работает от root).
        """
        path = os.path.join(self._host_workspace_root, str(chat_id))
        os.makedirs(path, exist_ok=True)
        try:
            os.chown(path, 10001, 10001)
        except (PermissionError, OSError) as exc:
            # На macOS Docker Desktop chown иногда падает — это OK,
            # потому что там uid-маппинг сделан иначе. Логируем и едем дальше.
            logger.debug("workspace chown skipped: %s", exc)
        return path

    # ── create / start / stop / remove ───────────────────────────────────────

    async def ensure_running(
        self,
        *,
        chat_id: uuid.UUID,
        existing_container_id: str | None,
    ) -> tuple[str, str]:
        """
        Гарантирует что контейнер для чата существует и запущен.
        Возвращает (container_id, container_name).
        """
        return await asyncio.to_thread(
            self._ensure_running_sync, chat_id, existing_container_id
        )

    def _ensure_running_sync(
        self,
        chat_id: uuid.UUID,
        existing_container_id: str | None,
    ) -> tuple[str, str]:
        client = self._get_client()
        name = self._container_name(chat_id)

        # Если был старый — попробуем его поднять
        if existing_container_id:
            try:
                container = client.containers.get(existing_container_id)
                if container.status != "running":
                    container.start()
                return container.id, container.name
            except NotFound:
                pass  # пересоздадим ниже
            except APIError as exc:
                logger.warning("docker get failed: %s", exc)

        # Проверим что образ существует ДО попытки run — даём понятную ошибку
        # без побочного эффекта (попытка запуска с pull может зависнуть в офлайне)
        try:
            client.images.get(self._image)
        except ImageNotFound:
            raise SandboxError(
                f"Образ {self._image} не собран на этом хосте. "
                f"Выполните: `make sandbox-build` "
                f"(или `docker build -t {self._image} backend/sandbox/`). "
                f"Сборка делается один раз, ~3-5 минут."
            )
        except APIError as exc:
            raise SandboxError(f"docker images.get failed: {exc}") from exc

        # Пересоздать (вдруг старый контейнер с этим именем остался)
        try:
            old = client.containers.get(name)
            try:
                old.remove(force=True)
            except APIError:
                pass
        except NotFound:
            pass

        # NB: Для bind-mount Docker daemon принимает путь как видит ХОСТ.
        # Если backend в контейнере — это НЕ наш `workspace_for(...)`, а его
        # «внешний» эквивалент (см. host_workspace_root_external).
        workspace_host = os.path.join(
            self._host_workspace_root_external, str(chat_id)
        )

        # Запуск
        try:
            container = client.containers.run(
                image=self._image,
                name=name,
                detach=True,
                tty=False,
                stdin_open=True,
                working_dir=self._container_workspace,
                # tail -f /dev/null — держит контейнер живым, реальные команды
                # запускаем через `docker exec`
                command=["sh", "-c", "tail -f /dev/null"],
                volumes={
                    workspace_host: {
                        "bind": self._container_workspace,
                        "mode": "rw",
                    },
                },
                # Ресурсы
                mem_limit=self._mem_limit,
                cpu_period=100_000,
                cpu_quota=self._cpu_quota,
                pids_limit=256,
                # Безопасность: без новых привилегий, read-only root FS,
                # /tmp как tmpfs (нужен для apt/pip кэшей)
                security_opt=["no-new-privileges:true"],
                read_only=False,  # write нужен для apt/pip install
                # Сеть — отдельная (для возможного firewalling в будущем)
                network=self._network if self._network_exists(client) else "bridge",
                # Не показываем хост-юзеру id чата в env
                environment={"HOME": "/workspace", "TERM": "xterm-256color"},
                # Пользователь — sandbox-юзер из образа (uid 10001)
                user="10001:10001",
                # Авто-удалить если упадёт
                auto_remove=False,
                labels={
                    "khasa.sandbox": "true",
                    "khasa.chat_id": str(chat_id),
                },
            )

            # Гарантируем что bind-mount /workspace доступен на запись юзеру 10001.
            # На Linux это обычно уже сделал хост-chown, но в Docker Desktop
            # (macOS/Windows) uid-маппинг другой и hostside chown не помогает.
            # Делаем chown ВНУТРИ контейнера от root — это всегда сработает.
            try:
                client.api.exec_start(
                    client.api.exec_create(
                        container.id,
                        cmd=["chown", "-R", "10001:10001", self._container_workspace],
                        user="root",
                    )["Id"],
                )
            except APIError as exc:
                logger.warning("workspace chown inside container failed: %s", exc)

            return container.id, container.name
        except ImageNotFound:
            raise SandboxError(
                f"Образ {self._image} не найден. "
                f"Соберите: cd backend/sandbox && docker build -t {self._image} ."
            )
        except APIError as exc:
            raise SandboxError(f"docker run failed: {exc}") from exc

    def _network_exists(self, client: docker.DockerClient) -> bool:
        try:
            client.networks.get(self._network)
            return True
        except NotFound:
            return False

    async def stop(self, container_id: str) -> None:
        await asyncio.to_thread(self._stop_sync, container_id)

    def _stop_sync(self, container_id: str) -> None:
        client = self._get_client()
        try:
            c = client.containers.get(container_id)
            c.stop(timeout=5)
        except NotFound:
            pass
        except APIError as exc:
            logger.warning("docker stop failed: %s", exc)

    async def remove(self, container_id: str) -> None:
        await asyncio.to_thread(self._remove_sync, container_id)

    def _remove_sync(self, container_id: str) -> None:
        client = self._get_client()
        try:
            c = client.containers.get(container_id)
            c.remove(force=True)
        except NotFound:
            pass
        except APIError as exc:
            logger.warning("docker rm failed: %s", exc)

    # ── exec ─────────────────────────────────────────────────────────────────

    async def exec(
        self,
        container_id: str,
        command: list[str] | str,
        *,
        workdir: str | None = None,
        timeout: int | None = None,
        user: str = "10001:10001",
    ) -> ExecResult:
        """
        Запуск команды в контейнере. Возвращает stdout/stderr/exit_code.

        По умолчанию — от непривилегированного юзера sandbox (uid 10001).
        Для админ-операций можно передать `user="root"`.
        """
        return await asyncio.to_thread(
            self._exec_sync, container_id, command, workdir, timeout, user
        )

    def _exec_sync(
        self,
        container_id: str,
        command,
        workdir: str | None,
        timeout: int | None,
        user: str,
    ) -> ExecResult:
        client = self._get_client()
        try:
            c = client.containers.get(container_id)
        except NotFound:
            return ExecResult(exit_code=127, stdout="", stderr="container not found")

        if isinstance(command, str):
            command = ["sh", "-c", command]

        try:
            exec_id = client.api.exec_create(
                c.id,
                cmd=command,
                workdir=workdir or self._container_workspace,
                user=user,
                tty=False,
                stdout=True,
                stderr=True,
            )["Id"]
            output = client.api.exec_start(exec_id, demux=True, stream=False)
            stdout_b, stderr_b = output if isinstance(output, tuple) else (output, b"")
            info = client.api.exec_inspect(exec_id)
            return ExecResult(
                exit_code=info.get("ExitCode") or 0,
                stdout=(stdout_b or b"").decode(errors="replace"),
                stderr=(stderr_b or b"").decode(errors="replace"),
            )
        except APIError as exc:
            return ExecResult(exit_code=1, stdout="", stderr=f"docker exec failed: {exc}")

    # ── listing for admin ────────────────────────────────────────────────────

    async def list_containers(self) -> list[dict]:
        return await asyncio.to_thread(self._list_sync)

    def _list_sync(self) -> list[dict]:
        client = self._get_client()
        out: list[dict] = []
        try:
            for c in client.containers.list(
                all=True, filters={"label": "khasa.sandbox=true"}
            ):
                out.append({
                    "container_id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "labels": dict(c.labels or {}),
                    "image": c.image.tags[0] if c.image.tags else str(c.image.id),
                })
        except APIError as exc:
            logger.warning("docker list failed: %s", exc)
        return out

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _container_name(chat_id: uuid.UUID) -> str:
        return f"khasa-sandbox-{str(chat_id)[:12]}"
