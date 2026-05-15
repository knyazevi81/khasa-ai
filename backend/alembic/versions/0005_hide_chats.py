"""chats.is_hidden flag

Revision ID: 0005_hide_chats
Revises: 0004_sandbox_mcp
Create Date: 2026-05-15 10:00:00

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_hide_chats"
down_revision: Union[str, None] = "0004_sandbox_mcp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column(
            "is_hidden",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_chats_user_hidden", "chats", ["user_id", "is_hidden"])


def downgrade() -> None:
    op.drop_index("ix_chats_user_hidden", table_name="chats")
    op.drop_column("chats", "is_hidden")
