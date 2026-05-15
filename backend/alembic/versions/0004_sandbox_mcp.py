"""sandboxes + mcp_servers

Revision ID: 0004_sandbox_mcp
Revises: 0003_artifacts
Create Date: 2026-05-15 09:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_sandbox_mcp"
down_revision: Union[str, None] = "0003_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sandboxes ────────────────────────────────────────────────────────────
    op.create_table(
        "sandboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("container_name", sa.String(length=255), nullable=False),
        sa.Column("image", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="created"),
        sa.Column("workspace_path", sa.String(length=500), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chat_id", name="uq_sandboxes_chat"),
    )
    op.create_index("ix_sandboxes_chat_id", "sandboxes", ["chat_id"])
    op.create_index("ix_sandboxes_user_id", "sandboxes", ["user_id"])

    # ── mcp_servers ──────────────────────────────────────────────────────────
    op.create_table(
        "mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("transport", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("command", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tools_cache", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_mcp_servers_user_id", "mcp_servers", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_servers_user_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
    op.drop_index("ix_sandboxes_user_id", table_name="sandboxes")
    op.drop_index("ix_sandboxes_chat_id", table_name="sandboxes")
    op.drop_table("sandboxes")
