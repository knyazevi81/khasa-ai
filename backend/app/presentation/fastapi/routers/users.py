import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.users import UserService
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import get_current_user, get_user_service
from app.presentation.fastapi.schemas.schemas import (
    AdminChangePasswordRequest,
    ChangeMyPasswordRequest,
    MessageResponse,
    NotificationSentResponse,
    SendToAllRequest,
    SendToUserRequest,
    UserResponse,
    UsersListResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="Мой профиль")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    user = await user_service.get_me(current_user.id)
    return UserResponse(**user.model_dump())


@router.patch(
    "/me/password",
    response_model=MessageResponse,
    summary="Сменить свой пароль",
)
async def change_my_password(
    body: ChangeMyPasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> MessageResponse:
    await user_service.change_my_password(current_user, body.old_password, body.new_password)
    return MessageResponse(message="Пароль успешно изменён")


# ── Admin ────────────────────────────────────────────────────────────────────


@router.get(
    "/",
    response_model=UsersListResponse,
    summary="[Admin] Все пользователи",
)
async def get_all_users(
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UsersListResponse:
    users = await user_service.get_all_users(current_user)
    return UsersListResponse(
        users=[UserResponse(**u.model_dump()) for u in users],
        total=len(users),
    )


@router.get(
    "/pending",
    response_model=UsersListResponse,
    summary="[Admin] Ожидают одобрения (email подтверждён, ждут активации)",
)
async def get_pending_users(
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UsersListResponse:
    users = await user_service.get_pending_users(current_user)
    return UsersListResponse(
        users=[UserResponse(**u.model_dump()) for u in users],
        total=len(users),
    )


@router.patch(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="[Admin] Активировать (одобрить заявку)",
)
async def activate_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    user = await user_service.activate_user(user_id, current_user)
    return UserResponse(**user.model_dump())


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="[Admin] Деактивировать пользователя",
)
async def deactivate_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    user = await user_service.deactivate_user(user_id, current_user)
    return UserResponse(**user.model_dump())


@router.patch(
    "/admin/change-password",
    response_model=MessageResponse,
    summary="[Admin] Сменить пароль любому пользователю",
)
async def admin_change_password(
    body: AdminChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> MessageResponse:
    await user_service.admin_change_password(body.user_id, body.new_password, current_user)
    return MessageResponse(message="Пароль изменён")


@router.post(
    "/notifications/all",
    response_model=NotificationSentResponse,
    summary="[Admin] Рассылка всем активным пользователям",
)
async def notify_all(
    body: SendToAllRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> NotificationSentResponse:
    count = await user_service.send_notification_to_all(body.subject, body.message, current_user)
    return NotificationSentResponse(sent_to=count, message=f"Отправлено {count} пользователям")


@router.post(
    "/notifications/user",
    response_model=MessageResponse,
    summary="[Admin] Уведомление конкретному пользователю",
)
async def notify_user(
    body: SendToUserRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> MessageResponse:
    await user_service.send_notification_to_user(
        body.user_id, body.subject, body.message, current_user
    )
    return MessageResponse(message="Уведомление отправлено")
