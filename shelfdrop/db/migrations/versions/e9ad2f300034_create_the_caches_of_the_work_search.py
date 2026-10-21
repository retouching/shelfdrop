"""Create the caches of the work search.

Revision ID: e9ad2f300034
Revises:
Create Date: 2026-10-21 14:56:51.865542

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9ad2f300034"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cached_works",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("work", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cached_works")),
    )
    with op.batch_alter_table("cached_works", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_cached_works_expires_at"), ["expires_at"], unique=False
        )

    op.create_table(
        "source_answers",
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("query", sa.String(length=300), nullable=False),
        sa.Column("candidates", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("source", "query", name=op.f("pk_source_answers")),
    )
    with op.batch_alter_table("source_answers", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_source_answers_expires_at"), ["expires_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("source_answers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_source_answers_expires_at"))

    op.drop_table("source_answers")
    with op.batch_alter_table("cached_works", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cached_works_expires_at"))

    op.drop_table("cached_works")
