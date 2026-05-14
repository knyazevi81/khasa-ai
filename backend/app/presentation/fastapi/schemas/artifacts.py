from __future__ import annotations

import uuid

from pydantic import BaseModel


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    slug: str
    kind: str
    title: str
    language: str | None
    current_version_id: uuid.UUID | None


class ArtifactVersionResponse(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    version_no: int
    content: str
    message_id: uuid.UUID


class ArtifactListResponse(BaseModel):
    artifacts: list[ArtifactResponse]
    total: int


class ArtifactDetailResponse(BaseModel):
    artifact: ArtifactResponse
    versions: list[ArtifactVersionResponse]


class SetVersionRequest(BaseModel):
    version_id: uuid.UUID
