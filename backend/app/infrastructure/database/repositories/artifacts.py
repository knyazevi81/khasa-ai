from __future__ import annotations

import uuid

from sqlalchemy import desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.artifact import Artifact, ArtifactVersion
from app.infrastructure.database.orm.models import Artifacts, ArtifactVersions
from app.infrastructure.database.repositories.base import ModelBaseRepository


class SQLArtifactRepository(ModelBaseRepository[Artifacts]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Artifacts)

    async def get_by_id(self, artifact_id: uuid.UUID) -> Artifact | None:
        result = await self.session.execute(select(Artifacts).filter_by(id=artifact_id))
        obj = result.scalar_one_or_none()
        return Artifact.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> Artifact | None:
        result = await self.session.execute(select(Artifacts).filter_by(**filter_by))
        obj = result.scalars().first()
        return Artifact.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[Artifact]:
        result = await self.session.execute(select(Artifacts).filter_by(**filter_by))
        return [Artifact.model_validate(o) for o in result.scalars().all()]

    async def get_by_chat_and_slug(
        self, chat_id: uuid.UUID, slug: str
    ) -> Artifact | None:
        result = await self.session.execute(
            select(Artifacts).where(
                Artifacts.chat_id == chat_id, Artifacts.slug == slug
            )
        )
        obj = result.scalars().first()
        return Artifact.model_validate(obj) if obj else None

    async def find_for_chat(self, chat_id: uuid.UUID) -> list[Artifact]:
        result = await self.session.execute(
            select(Artifacts)
            .where(Artifacts.chat_id == chat_id)
            .order_by(desc(Artifacts.updated_at))
        )
        return [Artifact.model_validate(o) for o in result.scalars().all()]

    async def add(self, **data) -> None:
        await self.session.execute(insert(Artifacts).values(**data))

    async def update_fields(self, artifact_id: uuid.UUID, **fields) -> None:
        await self.session.execute(
            update(Artifacts).where(Artifacts.id == artifact_id).values(**fields)
        )


class SQLArtifactVersionRepository(ModelBaseRepository[ArtifactVersions]):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ArtifactVersions)

    async def get_by_id(self, version_id: uuid.UUID) -> ArtifactVersion | None:
        result = await self.session.execute(
            select(ArtifactVersions).filter_by(id=version_id)
        )
        obj = result.scalar_one_or_none()
        return ArtifactVersion.model_validate(obj) if obj else None

    async def find_one_or_none(self, **filter_by) -> ArtifactVersion | None:
        result = await self.session.execute(
            select(ArtifactVersions).filter_by(**filter_by)
        )
        obj = result.scalars().first()
        return ArtifactVersion.model_validate(obj) if obj else None

    async def find_all(self, **filter_by) -> list[ArtifactVersion]:
        result = await self.session.execute(
            select(ArtifactVersions).filter_by(**filter_by)
        )
        return [ArtifactVersion.model_validate(o) for o in result.scalars().all()]

    async def find_for_artifact(
        self, artifact_id: uuid.UUID
    ) -> list[ArtifactVersion]:
        result = await self.session.execute(
            select(ArtifactVersions)
            .where(ArtifactVersions.artifact_id == artifact_id)
            .order_by(ArtifactVersions.version_no.asc())
        )
        return [ArtifactVersion.model_validate(o) for o in result.scalars().all()]

    async def next_version_no(self, artifact_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(ArtifactVersions.version_no)
            .where(ArtifactVersions.artifact_id == artifact_id)
            .order_by(desc(ArtifactVersions.version_no))
            .limit(1)
        )
        last = result.scalar_one_or_none()
        return (last or 0) + 1

    async def add(self, **data) -> None:
        await self.session.execute(insert(ArtifactVersions).values(**data))
