"""Keep the files to place by hand.

The files of the page Ranger (plan section 3, point 5): the downloads the worker did not place
alone and the files of the libraries the scan found misplaced, what they hold, and what the page
asked the worker to do with them.

Revision ID: e24f8ad607d1
Revises: 13745d9b70d2
Create Date: 2026-10-21 21:46:10.993988

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e24f8ad607d1"
down_revision: str | Sequence[str] | None = "13745d9b70d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "place_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=10), nullable=False),
        sa.Column("download_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=True),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("files", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=True),
        sa.Column("chapters", sa.Text(), nullable=False),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("existing", sa.Text(), nullable=False),
        sa.Column("work_id", sa.String(length=200), nullable=True),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("request", sa.Text(), nullable=True),
        sa.Column("error", sa.String(length=20), nullable=True),
        sa.Column("destination", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_items")),
    )
    with op.batch_alter_table("place_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_place_items_download_id"), ["download_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_place_items_path"), ["path"], unique=False)
        batch_op.create_index(batch_op.f("ix_place_items_state"), ["state"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("place_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_place_items_state"))
        batch_op.drop_index(batch_op.f("ix_place_items_path"))
        batch_op.drop_index(batch_op.f("ix_place_items_download_id"))

    op.drop_table("place_items")
