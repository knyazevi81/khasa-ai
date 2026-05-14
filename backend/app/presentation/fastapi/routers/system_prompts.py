from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.system_prompts import SystemPromptService
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import (
    get_current_user,
    get_system_prompt_service,
)
from app.presentation.fastapi.schemas.schemas import MessageResponse
from app.presentation.fastapi.schemas.system_prompts import (
    SystemPromptCreateRequest,
    SystemPromptListResponse,
    SystemPromptResponse,
    SystemPromptUpdateRequest,
)

router = APIRouter(prefix="/system-prompts", tags=["system-prompts"])


@router.get("/", response_model=SystemPromptListResponse)
async def list_prompts(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptListResponse:
    rows = await service.list_for_user(current_user.id)
    return SystemPromptListResponse(
        prompts=[SystemPromptResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("/", response_model=SystemPromptResponse, status_code=201)
async def create_prompt(
    body: SystemPromptCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptResponse:
    row = await service.create(
        user_id=current_user.id,
        title=body.title,
        content=body.content,
        description=body.description,
        icon=body.icon,
    )
    return SystemPromptResponse.model_validate(row)


@router.patch("/{prompt_id}", response_model=SystemPromptResponse)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: SystemPromptUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> SystemPromptResponse:
    row = await service.update(
        prompt_id=prompt_id,
        user_id=current_user.id,
        **body.model_dump(exclude_unset=True),
    )
    return SystemPromptResponse.model_validate(row)


@router.delete("/{prompt_id}", response_model=MessageResponse)
async def delete_prompt(
    prompt_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SystemPromptService, Depends(get_system_prompt_service)],
) -> MessageResponse:
    await service.delete(prompt_id, current_user.id)
    return MessageResponse(message="Удалено")
