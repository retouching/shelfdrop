"""Keep the downloads sent to qBittorrent.

The releases sent, their torrents and their ids, what they are for (the work, the author, the
series, the volumes, the kind and the mode), their stage, their attempts and who asked.

Revision ID: e88f18e15668
Revises: 568e93e7e2dc
Create Date: 2026-10-21 18:56:39.224983

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e88f18e15668"
down_revision: str | Sequence[str] | None = "568e93e7e2dc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "downloads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("info_hash", sa.String(length=40), nullable=True),
        sa.Column("torrent", sa.LargeBinary(), nullable=True),
        sa.Column("magnet", sa.Text(), nullable=True),
        sa.Column("release_id", sa.String(length=16), nullable=False),
        sa.Column("guid", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("indexer_id", sa.Integer(), nullable=False),
        sa.Column("indexer", sa.String(length=200), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.Column("work_id", sa.String(length=200), nullable=True),
        sa.Column("work_name", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("series", sa.String(length=200), nullable=False),
        sa.Column("volume_kind", sa.String(length=10), nullable=False),
        sa.Column("volume_first", sa.Integer(), nullable=True),
        sa.Column("volume_last", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=10), nullable=False),
        sa.Column("failure", sa.String(length=20), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("added_at", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_downloads")),
    )
    with op.batch_alter_table("downloads", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_downloads_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_downloads_info_hash"), ["info_hash"], unique=False)
        batch_op.create_index(batch_op.f("ix_downloads_stage"), ["stage"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("downloads", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_downloads_stage"))
        batch_op.drop_index(batch_op.f("ix_downloads_info_hash"))
        batch_op.drop_index(batch_op.f("ix_downloads_created_at"))

    op.drop_table("downloads")
