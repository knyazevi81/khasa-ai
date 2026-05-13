from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.llm_credentials import LLMCredentialService
from app.domain.models.llm import LLMProvider
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import (
    get_current_user,
    get_llm_credential_service,
)
from app.presentation.fastapi.schemas.llm import (
    LLMCredentialCreateRequest,
    LLMCredentialResponse,
    LLMCredentialUpdateRequest,
    LLMCredentialsListResponse,
    mask_secret,
)
from app.presentation.fastapi.schemas.schemas import MessageResponse

router = APIRouter(prefix="/llm/credentials", tags=["llm"])


def _to_response(c) -> LLMCredentialResponse:
    return LLMCredentialResponse(
        id=c.id,
        provider=c.provider.value if hasattr(c.provider, "value") else str(c.provider),
        label=c.label,
        secret_mask=mask_secret(c.secret),
        base_url=c.base_url,
        default_model=c.default_model,
        is_active=c.is_active,
    )


@router.get("/", response_model=LLMCredentialsListResponse, summary="Мои LLM-ключи")
async def list_credentials(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LLMCredentialService, Depends(get_llm_credential_service)],
) -> LLMCredentialsListResponse:
    creds = await service.list_for_user(current_user.id)
    return LLMCredentialsListResponse(
        credentials=[_to_response(c) for c in creds],
        total=len(creds),
    )


@router.post(
    "/",
    response_model=LLMCredentialResponse,
    status_code=201,
    summary="Добавить ключ LLM",
)
async def create_credential(
    body: LLMCredentialCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LLMCredentialService, Depends(get_llm_credential_service)],
) -> LLMCredentialResponse:
    cred = await service.create(
        user_id=current_user.id,
        provider=LLMProvider(body.provider),
        label=body.label,
        secret=body.secret,
        base_url=body.base_url,
        default_model=body.default_model,
    )
    return _to_response(cred)


@router.patch("/{credential_id}", response_model=LLMCredentialResponse)
async def update_credential(
    credential_id: uuid.UUID,
    body: LLMCredentialUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LLMCredentialService, Depends(get_llm_credential_service)],
) -> LLMCredentialResponse:
    cred = await service.update(
        credential_id=credential_id,
        user_id=current_user.id,
        **body.model_dump(exclude_unset=True),
    )
    return _to_response(cred)


@router.delete("/{credential_id}", response_model=MessageResponse)
async def delete_credential(
    credential_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LLMCredentialService, Depends(get_llm_credential_service)],
) -> MessageResponse:
    await service.delete(credential_id, current_user.id)
    return MessageResponse(message="Удалено")


@router.post("/{credential_id}/validate", response_model=MessageResponse)
async def validate_credential(
    credential_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[LLMCredentialService, Depends(get_llm_credential_service)],
) -> MessageResponse:
    await service.validate(credential_id, current_user.id)
    return MessageResponse(message="Ключ валиден")
