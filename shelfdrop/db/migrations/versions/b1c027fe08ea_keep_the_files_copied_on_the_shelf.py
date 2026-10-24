"""Keep the files copied on the shelf.

The setting `placement.mode` may copy a file of a download rather than hardlink it: the file of
the shelf keeps the file of the torrent it is a copy of (Ranger leaves it aside), and the
download and the file of Ranger it was placed from are marked copied for the page.

Revision ID: b1c027fe08ea
Revises: 36a54aec2e2c
Create Date: 2026-10-24 14:27:36.156857

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c027fe08ea"
down_revision: str | Sequence[str] | None = "36a54aec2e2c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("downloads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("copied", sa.Boolean(), server_default="0", nullable=False))

    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("copied_from", sa.Text(), nullable=True))

    with op.batch_alter_table("place_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("copied", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("place_items", schema=None) as batch_op:
        batch_op.drop_column("copied")

    with op.batch_alter_table("files", schema=None) as batch_op:
        batch_op.drop_column("copied_from")

    with op.batch_alter_table("downloads", schema=None) as batch_op:
        batch_op.drop_column("copied")
