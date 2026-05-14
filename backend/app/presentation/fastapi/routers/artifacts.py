from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.artifacts import ArtifactService
from app.application.use_cases.chat import ChatService
from app.domain.models.models import User
from app.presentation.fastapi.dependencies import (
    get_artifact_service,
    get_chat_service,
    get_current_user,
)
from app.presentation.fastapi.schemas.artifacts import (
    ArtifactDetailResponse,
    ArtifactListResponse,
    ArtifactResponse,
    ArtifactVersionResponse,
    SetVersionRequest,
)

router = APIRouter(prefix="/chats", tags=["artifacts"])


def _to_resp(a) -> ArtifactResponse:
    return ArtifactResponse(
        id=a.id,
        chat_id=a.chat_id,
        slug=a.slug,
        kind=a.kind,
        title=a.title,
        language=a.language,
        current_version_id=a.current_version_id,
    )


def _to_version(v) -> ArtifactVersionResponse:
    return ArtifactVersionResponse(
        id=v.id,
        artifact_id=v.artifact_id,
        version_no=v.version_no,
        content=v.content,
        message_id=v.message_id,
    )


@router.get(
    "/{chat_id}/artifacts",
    response_model=ArtifactListResponse,
    summary="Артефакты чата",
)
async def list_artifacts(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    artifact_service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> ArtifactListResponse:
    # Проверка владения через chat_service.get_chat
    await chat_service.get_chat(chat_id, current_user.id)
    arts = await artifact_service.list_for_chat(chat_id)
    return ArtifactListResponse(
        artifacts=[_to_resp(a) for a in arts],
        total=len(arts),
    )


@router.get(
    "/{chat_id}/artifacts/{artifact_id}",
    response_model=ArtifactDetailResponse,
    summary="Артефакт со всеми версиями",
)
async def get_artifact(
    chat_id: uuid.UUID,
    artifact_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    artifact_service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> ArtifactDetailResponse:
    await chat_service.get_chat(chat_id, current_user.id)
    art = await artifact_service.get(artifact_id)
    versions = await artifact_service.list_versions(artifact_id)
    return ArtifactDetailResponse(
        artifact=_to_resp(art),
        versions=[_to_version(v) for v in versions],
    )


@router.post(
    "/{chat_id}/artifacts/{artifact_id}/set-version",
    response_model=ArtifactResponse,
    summary="Переключить активную версию артефакта",
)
async def set_version(
    chat_id: uuid.UUID,
    artifact_id: uuid.UUID,
    body: SetVersionRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
    artifact_service: Annotated[ArtifactService, Depends(get_artifact_service)],
) -> ArtifactResponse:
    await chat_service.get_chat(chat_id, current_user.id)
    art = await artifact_service.set_current_version(artifact_id, body.version_id)
    return _to_resp(art)
