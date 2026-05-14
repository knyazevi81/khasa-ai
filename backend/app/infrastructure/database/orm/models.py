from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class Users(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Подтвердил email кодом из письма
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Одобрен админом — может логиниться
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    verification_codes: Mapped[list["EmailVerificationCodes"]] = relationship(
        "EmailVerificationCodes",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class EmailVerificationCodes(Base):
    """
    Одноразовые 6-значные коды для подтверждения email.
    Храним хэш кода — даже в логах/дампах БД код «голым» не лежит.
    """
    __tablename__ = "email_verification_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["Users"] = relationship("Users", back_populates="verification_codes")


# ── LLM credentials (ключи API провайдеров, хранятся зашифрованными) ──────────


class LLMCredentials(Base):
    __tablename__ = "llm_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    # Fernet-зашифрованный ключ (для Ollama — может быть пустым/мусором)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Чат и сообщения (граф) ────────────────────────────────────────────────────


class Chats(Base):
    """
    Чат — корень графа сообщений.
    `current_message_id` указывает на «активный» лист в дереве — это то,
    что фронт показывает как текущую ветку.
    """
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Новый чат")

    # ID активного листа (для перехода между ветками). NULL = пустой чат.
    current_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Какие LLM-настройки использовать по умолчанию для этого чата
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("llm_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Включает агентный режим: ассистент сначала декомпозирует задачу на
    # подзадачи (AgentSubtasks), потом исполняет.
    agent_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Messages(Base):
    """
    Узел графа. Хранит ссылку на parent (то сообщение, после которого идёт
    это) — дерево. У одного parent может быть N детей: это и есть ветки.
    """
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)        # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Имя ветки, начинающейся от этого узла — опциональное (main, alt-a, ...)
    branch_label: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Стэк состояний: pending → streaming → ready / failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")

    # Метаданные провайдера (модель, токены)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Attachments(Base):
    """
    Прикреплённые к user-сообщению файлы.
    Контент извлечён в `extracted_text` — оригинал не храним (это нам не нужно для LLM).
    """
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # txt | pdf
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")


class AgentSubtasks(Base):
    """
    Подзадачи агентного режима. Привязаны к сообщению ассистента —
    показывают «что ассистент сейчас делает».
    Статусы: pending → running → done / failed.
    """
    __tablename__ = "agent_subtasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Artifacts (отдельные документы рядом с чатом) ────────────────────────────


class Artifacts(Base):
    """
    Артефакт — самостоятельный документ, который ассистент создаёт и
    обновляет в ходе диалога. У одного артефакта может быть много версий —
    активная задаётся `current_version_id`.

    Уникальность `(chat_id, slug)` позволяет LLM ссылаться на «этот же»
    артефакт между сообщениями и инкрементировать версии.
    """
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("chat_id", "slug", name="uq_artifacts_chat_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class ArtifactVersions(Base):
    __tablename__ = "artifact_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


# ── System prompts (library) ─────────────────────────────────────────────────


class SystemPrompts(Base):
    """
    Библиотека пользовательских system-промптов. Юзер может создать «роль»
    («помощник по python», «редактор», «переводчик с английского»), назвать
    её и потом выбирать при создании чата.
    """
    __tablename__ = "system_prompts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Эмодзи или короткий ярлык для UI («🐍», «✏️», «🌍»)
    icon: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
