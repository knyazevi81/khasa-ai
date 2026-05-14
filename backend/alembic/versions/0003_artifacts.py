"""artifacts + system_prompts

Revision ID: 0003_artifacts
Revises: 0002_chats
Create Date: 2026-05-14 09:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_artifacts"
down_revision: Union[str, None] = "0002_chats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── artifacts ────────────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("language", sa.String(length=40), nullable=True),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chat_id", "slug", name="uq_artifacts_chat_slug"),
    )
    op.create_index("ix_artifacts_chat_id", "artifacts", ["chat_id"])

    # ── artifact_versions ────────────────────────────────────────────────────
    op.create_table(
        "artifact_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_artifact_versions_artifact_id", "artifact_versions", ["artifact_id"])
    op.create_index("ix_artifact_versions_message_id", "artifact_versions", ["message_id"])

    op.create_foreign_key(
        "fk_artifacts_current_version_id",
        "artifacts",
        "artifact_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ── system_prompts ───────────────────────────────────────────────────────
    op.create_table(
        "system_prompts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("icon", sa.String(length=8), nullable=True),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_system_prompts_user_id", "system_prompts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_system_prompts_user_id", table_name="system_prompts")
    op.drop_table("system_prompts")
    op.drop_constraint("fk_artifacts_current_version_id", "artifacts", type_="foreignkey")
    op.drop_index("ix_artifact_versions_message_id", table_name="artifact_versions")
    op.drop_index("ix_artifact_versions_artifact_id", table_name="artifact_versions")
    op.drop_table("artifact_versions")
    op.drop_index("ix_artifacts_chat_id", table_name="artifacts")
    op.drop_table("artifacts")
