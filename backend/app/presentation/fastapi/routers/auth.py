from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.application.use_cases.auth import AuthService
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import get_auth_service, get_current_user
from app.presentation.fastapi.schemas.schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendCodeRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация (шаг 1) — создаёт юзера и шлёт код на email",
)
async def register(
    body: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    user = await auth_service.register(body.email, body.password)
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        is_superuser=user.is_superuser,
    )


@router.post(
    "/verify-email",
    response_model=UserResponse,
    summary="Регистрация (шаг 2) — подтвердить email кодом из письма",
)
async def verify_email(
    body: VerifyEmailRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    user = await auth_service.verify_email_code(body.email, body.code)
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_email_verified=user.is_email_verified,
        is_superuser=user.is_superuser,
    )


@router.post(
    "/resend-code",
    response_model=MessageResponse,
    summary="Регистрация — переотправить код подтверждения",
)
async def resend_code(
    body: ResendCodeRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    await auth_service.resend_verification_code(body.email)
    return MessageResponse(message="Если такой адрес зарегистрирован — код отправлен")


@router.post("/login", response_model=TokenResponse, summary="Логин — JWT-пара")
async def login(
    body: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    pair = await auth_service.login(body.email, body.password)
    return TokenResponse(**pair.model_dump())


@router.post("/refresh", response_model=TokenResponse, summary="Обновить токены")
async def refresh(
    body: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    pair = await auth_service.refresh(body.refresh_token)
    return TokenResponse(**pair.model_dump())


@router.get("/me", response_model=UserResponse, summary="Текущий пользователь")
async def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        is_email_verified=current_user.is_email_verified,
        is_superuser=current_user.is_superuser,
    )


@router.post("/logout", response_model=MessageResponse, summary="Выход (client-side)")
async def logout(
    _: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    return MessageResponse(message="Successfully logged out")
