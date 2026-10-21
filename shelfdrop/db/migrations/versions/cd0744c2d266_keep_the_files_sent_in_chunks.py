"""Keep the files sent in chunks.

The uploads of the page Manuel (plan section 3, point 6): their name, their size and their
chunks, the chunks received, their SHA-256 once checked and their state until the placement
worker lists them in Ranger.

Revision ID: cd0744c2d266
Revises: 1170143ab2d3
Create Date: 2026-10-21 23:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cd0744c2d266"
down_revision: str | Sequence[str] | None = "1170143ab2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("received", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
    )
    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_uploads_state"), ["state"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("uploads", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_uploads_state"))

    op.drop_table("uploads")
