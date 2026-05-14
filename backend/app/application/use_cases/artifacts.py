from __future__ import annotations

import uuid

from app.domain.exceptions.base import AppException
from app.domain.models.artifact import Artifact, ArtifactKind, ArtifactVersion
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.llm.artifact_parser import (
    ParsedArtifact,
    extract_artifacts,
    is_allowed_kind,
)


class ArtifactNotFoundError(AppException):
    code = 404
    message = "Артефакт не найден"


class ArtifactService:
    """
    Работа с артефактами чата.

    Главное — `upsert_from_stream`: ему скармливают накопленный текст
    assistant-сообщения, он извлекает все блоки `khasa-artifact:*` и:
      • если артефакта с таким slug ещё нет — создаёт + первую версию;
      • если есть, и контент новой версии отличается — добавляет версию
        и проматывает `current_version_id`.
    Возвращает список изменённых артефактов (для рассылки событий по WS).
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[Artifact]:
        return await self.uow.artifacts.find_for_chat(chat_id)

    async def get(self, artifact_id: uuid.UUID) -> Artifact:
        a = await self.uow.artifacts.get_by_id(artifact_id)
        if not a:
            raise ArtifactNotFoundError()
        return a

    async def get_version(self, version_id: uuid.UUID) -> ArtifactVersion:
        v = await self.uow.artifact_versions.get_by_id(version_id)
        if not v:
            raise ArtifactNotFoundError("Версия не найдена")
        return v

    async def list_versions(self, artifact_id: uuid.UUID) -> list[ArtifactVersion]:
        return await self.uow.artifact_versions.find_for_artifact(artifact_id)

    async def upsert_from_stream(
        self,
        *,
        chat_id: uuid.UUID,
        message_id: uuid.UUID,
        accumulated_text: str,
    ) -> list[Artifact]:
        """
        Идемпотентно парсит блоки и сохраняет/обновляет артефакты.
        Возвращает только изменённые (новые или с новой версией).
        """
        parsed = extract_artifacts(accumulated_text)
        if not parsed:
            return []

        changed: list[Artifact] = []
        for p in parsed:
            if not is_allowed_kind(p.kind):
                continue
            changed_one = await self._upsert_single(
                chat_id=chat_id, message_id=message_id, parsed=p
            )
            if changed_one:
                changed.append(changed_one)
        return changed

    async def _upsert_single(
        self,
        *,
        chat_id: uuid.UUID,
        message_id: uuid.UUID,
        parsed: ParsedArtifact,
    ) -> Artifact | None:
        existing = await self.uow.artifacts.get_by_chat_and_slug(chat_id, parsed.slug)

        if existing is None:
            # Новый артефакт — создаём + первая версия
            artifact_id = uuid.uuid4()
            await self.uow.artifacts.add(
                id=artifact_id,
                chat_id=chat_id,
                slug=parsed.slug,
                kind=parsed.kind,
                title=parsed.title,
                language=parsed.language,
                current_version_id=None,
            )
            version_id = uuid.uuid4()
            await self.uow.artifact_versions.add(
                id=version_id,
                artifact_id=artifact_id,
                version_no=1,
                content=parsed.content,
                message_id=message_id,
            )
            await self.uow.artifacts.update_fields(
                artifact_id, current_version_id=version_id
            )
            artifact = await self.uow.artifacts.get_by_id(artifact_id)
            return artifact

        # Уже есть. Если контент совпадает с последней версией — ничего не делаем.
        versions = await self.uow.artifact_versions.find_for_artifact(existing.id)
        latest = versions[-1] if versions else None
        if latest is not None and latest.content == parsed.content:
            return None  # no-op

        # Новая версия
        next_no = await self.uow.artifact_versions.next_version_no(existing.id)
        version_id = uuid.uuid4()
        await self.uow.artifact_versions.add(
            id=version_id,
            artifact_id=existing.id,
            version_no=next_no,
            content=parsed.content,
            message_id=message_id,
        )
        # Заодно обновим title/language если в этой версии они изменились
        fields: dict = {"current_version_id": version_id}
        if parsed.title and parsed.title != existing.title:
            fields["title"] = parsed.title
        if parsed.language and parsed.language != existing.language:
            fields["language"] = parsed.language
        await self.uow.artifacts.update_fields(existing.id, **fields)
        artifact = await self.uow.artifacts.get_by_id(existing.id)
        return artifact

    async def set_current_version(
        self, artifact_id: uuid.UUID, version_id: uuid.UUID
    ) -> Artifact:
        version = await self.uow.artifact_versions.get_by_id(version_id)
        if not version or version.artifact_id != artifact_id:
            raise ArtifactNotFoundError("Версия не принадлежит этому артефакту")
        await self.uow.artifacts.update_fields(
            artifact_id, current_version_id=version_id
        )
        return await self.get(artifact_id)
