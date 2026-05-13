from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.use_cases.auth import AuthService
from app.application.use_cases.chat import ChatService
from app.application.use_cases.llm_credentials import LLMCredentialService
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
from app.infrastructure.security.crypto import SecretCipher
from app.infrastructure.security.jwt import JoseTokenService
from app.infrastructure.security.password import BcryptPasswordHasher

bearer_scheme = HTTPBearer(auto_error=False)

# Синглтоны процессного скоупа — без состояния
_llm_router_singleton: LLMRouter | None = None


def get_llm_router() -> AbstractLLMRouter:
    global _llm_router_singleton
    if _llm_router_singleton is None:
        _llm_router_singleton = LLMRouter()
    return _llm_router_singleton


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
) -> ChatService:
    return ChatService(uow, cred_service, router)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    if credentials is None:
        raise NotAuthenticatedError()
    return await auth_service.get_current_user(credentials.credentials)
