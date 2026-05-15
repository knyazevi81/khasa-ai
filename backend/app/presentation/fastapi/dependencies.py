from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.use_cases.auth import AuthService
from app.application.use_cases.artifacts import ArtifactService
from app.application.use_cases.chat import ChatService
from app.application.use_cases.llm_credentials import LLMCredentialService
from app.application.use_cases.mcp_servers import MCPService
from app.application.use_cases.sandboxes import SandboxService
from app.application.use_cases.system_prompts import SystemPromptService
from app.application.use_cases.users import UserService
from app.domain.exceptions.base import NotAuthenticatedError
from app.domain.interface.email import AbstractEmailService
from app.domain.interface.llm import AbstractLLMRouter
from app.domain.models.models import User
from app.infrastructure.config.config import Settings, get_settings
from app.infrastructure.database.dependencies import get_uow
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.email.service import EmailService
from app.infrastructure.llm.router import LLMRouter
from app.infrastructure.sandbox.docker_manager import DockerSandboxManager
from app.infrastructure.security.crypto import SecretCipher
from app.infrastructure.security.jwt import JoseTokenService
from app.infrastructure.security.password import BcryptPasswordHasher
from app.infrastructure.skills.base import SkillRegistry
from app.infrastructure.skills.builtin import register_builtin_skills

bearer_scheme = HTTPBearer(auto_error=False)

# Синглтоны процессного скоупа — без состояния
_llm_router_singleton: LLMRouter | None = None
_sandbox_manager_singleton: DockerSandboxManager | None = None
_skill_registry_singleton: SkillRegistry | None = None


def get_llm_router() -> AbstractLLMRouter:
    global _llm_router_singleton
    if _llm_router_singleton is None:
        _llm_router_singleton = LLMRouter()
    return _llm_router_singleton


def get_sandbox_manager() -> DockerSandboxManager:
    global _sandbox_manager_singleton
    if _sandbox_manager_singleton is None:
        # WORKSPACES_HOST_PATH = путь к workspace-директории НА ХОСТЕ Docker.
        # Используется только для bind-mount sandbox-контейнеров — внутри
        # backend мы работаем со своим `/var/khasa/workspaces`.
        # Для compose с named volume `khasa_workspaces` стандартный путь:
        #   /var/lib/docker/volumes/khasa_workspaces/_data
        import os as _os
        external = _os.environ.get("WORKSPACES_HOST_PATH")
        _sandbox_manager_singleton = DockerSandboxManager(
            host_workspace_root_external=external,
        )
    return _sandbox_manager_singleton


def get_skill_registry() -> SkillRegistry:
    global _skill_registry_singleton
    if _skill_registry_singleton is None:
        r = SkillRegistry()
        register_builtin_skills(r)
        _skill_registry_singleton = r
    return _skill_registry_singleton


def get_secret_cipher(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SecretCipher:
    return SecretCipher(settings.SECRET_CIPHER_KEY.get_secret_value())


def get_password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def get_token_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> JoseTokenService:
    return JoseTokenService(settings)


def get_email_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AbstractEmailService:
    return EmailService(settings)


def get_auth_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    password_hasher: Annotated[BcryptPasswordHasher, Depends(get_password_hasher)],
    token_service: Annotated[JoseTokenService, Depends(get_token_service)],
    email_service: Annotated[AbstractEmailService, Depends(get_email_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(uow, password_hasher, token_service, email_service, settings)


def get_user_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    password_hasher: Annotated[BcryptPasswordHasher, Depends(get_password_hasher)],
    email_service: Annotated[AbstractEmailService, Depends(get_email_service)],
) -> UserService:
    return UserService(uow, password_hasher, email_service)


def get_llm_credential_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
    router: Annotated[AbstractLLMRouter, Depends(get_llm_router)],
) -> LLMCredentialService:
    return LLMCredentialService(uow, cipher, router)


def get_chat_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    cred_service: Annotated[LLMCredentialService, Depends(get_llm_credential_service)],
    router: Annotated[AbstractLLMRouter, Depends(get_llm_router)],
    sandbox_manager: Annotated[DockerSandboxManager, Depends(get_sandbox_manager)],
    skill_registry: Annotated[SkillRegistry, Depends(get_skill_registry)],
) -> ChatService:
    artifact_service = ArtifactService(uow)
    sandbox_service = SandboxService(uow, sandbox_manager)
    mcp_service = MCPService(uow)
    return ChatService(
        uow,
        cred_service,
        router,
        artifacts=artifact_service,
        sandbox_service=sandbox_service,
        mcp_service=mcp_service,
        skill_registry=skill_registry,
    )


def get_artifact_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> ArtifactService:
    return ArtifactService(uow)


def get_system_prompt_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> SystemPromptService:
    return SystemPromptService(uow)


def get_sandbox_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
    manager: Annotated[DockerSandboxManager, Depends(get_sandbox_manager)],
) -> SandboxService:
    return SandboxService(uow, manager)


def get_mcp_service(
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> MCPService:
    return MCPService(uow)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: str | None = None,
) -> User:
    """
    Аутентификация юзера.

    Обычно — через `Authorization: Bearer ...` (для AJAX и API).
    Дополнительно поддерживаем `?access_token=...` в query — это нужно
    для прямых GET-запросов (например, скачивание экспорта чата), где
    нельзя установить кастомный header.
    """
    token: str | None = None
    if credentials is not None:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        raise NotAuthenticatedError()
    return await auth_service.get_current_user(token)
