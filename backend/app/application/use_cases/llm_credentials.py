from __future__ import annotations

import uuid

from app.domain.exceptions.base import AppException, ForbiddenError, UserNotFoundError
from app.domain.interface.llm import AbstractLLMRouter
from app.domain.models.llm import LLMCredential, LLMProvider
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.security.crypto import SecretCipher


class CredentialNotFoundError(AppException):
    code = 404
    message = "LLM-credential не найден"


class InvalidCredentialError(AppException):
    code = 400
    message = "Ключ или endpoint LLM не работает"


class LLMCredentialService:
    """CRUD над LLM-ключами + валидация (попробовать постучаться в провайдер)."""

    def __init__(
        self,
        uow: UnitOfWork,
        cipher: SecretCipher,
        router: AbstractLLMRouter,
    ) -> None:
        self.uow = uow
        self.cipher = cipher
        self.router = router

    async def list_for_user(self, user_id: uuid.UUID) -> list[LLMCredential]:
        rows = await self.uow.llm_credentials.find_for_user(user_id)
        # Расшифровываем сразу — domain-слою удобнее работать с plaintext-credential.
        # Наружу (в API) secret уходит маской — это делается на уровне presentation.
        out: list[LLMCredential] = []
        for r in rows:
            out.append(
                LLMCredential(
                    id=r.id,
                    user_id=r.user_id,
                    provider=LLMProvider(r.provider),
                    label=r.label,
                    secret=self.cipher.decrypt(r.encrypted_secret),
                    base_url=r.base_url,
                    default_model=r.default_model,
                    is_active=r.is_active,
                )
            )
        return out

    async def get_for_user(
        self, credential_id: uuid.UUID, user_id: uuid.UUID
    ) -> LLMCredential:
        row = await self.uow.llm_credentials.get_by_id(credential_id)
        if not row or row.user_id != user_id:
            raise CredentialNotFoundError()
        return LLMCredential(
            id=row.id,
            user_id=row.user_id,
            provider=LLMProvider(row.provider),
            label=row.label,
            secret=self.cipher.decrypt(row.encrypted_secret),
            base_url=row.base_url,
            default_model=row.default_model,
            is_active=row.is_active,
        )

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        provider: LLMProvider,
        label: str,
        secret: str,
        base_url: str | None,
        default_model: str | None,
    ) -> LLMCredential:
        cred_id = uuid.uuid4()
        await self.uow.llm_credentials.add(
            id=cred_id,
            user_id=user_id,
            provider=provider.value,
            label=label,
            encrypted_secret=self.cipher.encrypt(secret or ""),
            base_url=base_url,
            default_model=default_model,
            is_active=True,
        )
        return LLMCredential(
            id=cred_id,
            user_id=user_id,
            provider=provider,
            label=label,
            secret=secret,
            base_url=base_url,
            default_model=default_model,
            is_active=True,
        )

    async def update(
        self,
        *,
        credential_id: uuid.UUID,
        user_id: uuid.UUID,
        label: str | None = None,
        secret: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        is_active: bool | None = None,
    ) -> LLMCredential:
        # Сначала проверим принадлежность
        await self.get_for_user(credential_id, user_id)

        fields: dict = {}
        if label is not None:
            fields["label"] = label
        if secret is not None:
            fields["encrypted_secret"] = self.cipher.encrypt(secret)
        if base_url is not None:
            fields["base_url"] = base_url
        if default_model is not None:
            fields["default_model"] = default_model
        if is_active is not None:
            fields["is_active"] = is_active

        if fields:
            await self.uow.llm_credentials.update_fields(credential_id, **fields)

        return await self.get_for_user(credential_id, user_id)

    async def delete(self, credential_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await self.uow.llm_credentials.delete_for_user(credential_id, user_id)

    async def validate(self, credential_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        cred = await self.get_for_user(credential_id, user_id)
        adapter = self.router.get(cred.provider.value)
        ok = await adapter.validate_credential(cred)
        if not ok:
            raise InvalidCredentialError()
        return True

    async def list_models(
        self, credential_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[str]:
        cred = await self.get_for_user(credential_id, user_id)
        adapter = self.router.get(cred.provider.value)
        return await adapter.list_models(cred)
