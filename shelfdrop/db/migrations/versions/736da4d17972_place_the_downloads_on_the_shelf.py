"""Place the downloads on the shelf.

The files the placement put on the shelf (`files`), the writes the API asks for in the
libraries (`library_tasks`), and the placement of each download: where it went, why it was
left to Ranger, the percent of its merge, when it ended.

Revision ID: 736da4d17972
Revises: a250a56263cc
Create Date: 2026-10-21 20:37:49.097852

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "736da4d17972"
down_revision: str | Sequence[str] | None = "a250a56263cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("download_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("work_id", sa.String(length=200), nullable=True),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("chapter", sa.Float(), nullable=True),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
    )
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_files_download_id"), ["download_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_files_series"), ["series"], unique=False)
        batch_op.create_index(batch_op.f("ix_files_work_id"), ["work_id"], unique=False)

    op.create_table(
        "library_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("done_at", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library_tasks")),
    )
    with op.batch_alter_table("library_tasks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_library_tasks_state"), ["state"], unique=False)

    with op.batch_alter_table("downloads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("destination", sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column("unplaced", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("placing_percent", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("placed_at", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("downloads", schema=None) as batch_op:
        batch_op.drop_column("placed_at")
        batch_op.drop_column("placing_percent")
        batch_op.drop_column("unplaced")
        batch_op.drop_column("destination")

    with op.batch_alter_table("library_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_library_tasks_state"))

    op.drop_table("library_tasks")
    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_files_work_id"))
        batch_op.drop_index(batch_op.f("ix_files_series"))
        batch_op.drop_index(batch_op.f("ix_files_download_id"))

    op.drop_table("files")
