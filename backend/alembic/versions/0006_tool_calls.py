"""tool_calls (persist agent tool invocations)

Revision ID: 0006_tool_calls
Revises: 0005_hide_chats
Create Date: 2026-05-15 11:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_tool_calls"
down_revision: Union[str, None] = "0005_hide_chats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Порядковый номер в рамках сообщения — чтобы рендерить в правильной
        # последовательности (модель может вызвать несколько tools подряд)
        sa.Column("order_idx", sa.Integer(), nullable=False, server_default="0"),
        # tool_use_id от LLM — нужен чтобы сматчить tool_result с tool_use
        sa.Column("tool_use_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        # Флаг: вывод — это спец-маркер present_files (фронт рендерит как «коробку с файлами»)
        sa.Column("is_present_files", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tool_calls_message_id", "tool_calls", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_calls_message_id", table_name="tool_calls")
    op.drop_table("tool_calls")
