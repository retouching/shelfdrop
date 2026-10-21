"""Keep the searches waiting.

The searches kept waiting (plan section 3, point 11): their work, their names, what they wait
for (any release, a volume, chapters), their state and their last search, and when they left
the list.

Revision ID: 13745d9b70d2
Revises: 736da4d17972
Create Date: 2026-10-21 21:07:30.809464

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "13745d9b70d2"
down_revision: str | Sequence[str] | None = "736da4d17972"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waiting_searches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("work_id", sa.String(length=200), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("author", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("names", sa.Text(), nullable=False),
        sa.Column("target", sa.String(length=10), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("chapter_from", sa.Float(), nullable=True),
        sa.Column("chapter_to", sa.Float(), nullable=True),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("releases", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column("searched_at", sa.Integer(), nullable=True),
        sa.Column("done_at", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_waiting_searches")),
    )
    with op.batch_alter_table("waiting_searches", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_waiting_searches_done_at"), ["done_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("waiting_searches", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_waiting_searches_done_at"))

    op.drop_table("waiting_searches")
