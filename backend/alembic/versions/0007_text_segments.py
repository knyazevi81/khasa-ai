"""message_text_segments (interleaved text + tool calls in assistant messages)

Revision ID: 0007_text_segments
Revises: 0006_tool_calls
Create Date: 2026-05-16 09:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_text_segments"
down_revision: Union[str, None] = "0006_tool_calls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_text_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Глобальный порядок в рамках сообщения (общий с tool_calls.order_idx).
        # При рендере фронт делает merge-sort по order_idx и получает
        # text/tool/text/tool/... в правильной последовательности.
        sa.Column("order_idx", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_message_text_segments_message_id",
        "message_text_segments",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_message_text_segments_message_id", table_name="message_text_segments")
    op.drop_table("message_text_segments")
