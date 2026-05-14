from __future__ import annotations

import uuid

from app.domain.exceptions.base import AppException
from app.infrastructure.database.orm.models import SystemPrompts
from app.infrastructure.database.uow import UnitOfWork


class SystemPromptNotFoundError(AppException):
    code = 404
    message = "Промпт не найден"


class SystemPromptService:
    """CRUD над пользовательскими system-промптами."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def list_for_user(self, user_id: uuid.UUID) -> list[SystemPrompts]:
        return await self.uow.system_prompts.find_for_user(user_id)

    async def get_for_user(
        self, prompt_id: uuid.UUID, user_id: uuid.UUID
    ) -> SystemPrompts:
        row = await self.uow.system_prompts.get_by_id(prompt_id)
        if not row or row.user_id != user_id:
            raise SystemPromptNotFoundError()
        return row

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        title: str,
        content: str,
        description: str | None = None,
        icon: str | None = None,
    ) -> SystemPrompts:
        prompt_id = uuid.uuid4()
        await self.uow.system_prompts.add(
            id=prompt_id,
            user_id=user_id,
            title=title,
            content=content,
            description=description,
            icon=icon,
            is_pinned=False,
        )
        return await self.get_for_user(prompt_id, user_id)

    async def update(
        self,
        *,
        prompt_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str | None = None,
        content: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        is_pinned: bool | None = None,
    ) -> SystemPrompts:
        await self.get_for_user(prompt_id, user_id)

        fields: dict = {}
        if title is not None:
            fields["title"] = title
        if content is not None:
            fields["content"] = content
        if description is not None:
            fields["description"] = description
        if icon is not None:
            fields["icon"] = icon
        if is_pinned is not None:
            fields["is_pinned"] = is_pinned

        if fields:
            await self.uow.system_prompts.update_fields(prompt_id, **fields)

        return await self.get_for_user(prompt_id, user_id)

    async def delete(self, prompt_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.uow.system_prompts.delete_for_user(prompt_id, user_id)
