"""Count the loose chapters of the shelf.

The chapters loose in the folder of the series of a release in chapters of Ranger: the page
counts a volume complete with them, as the placement does.

Revision ID: 1170143ab2d3
Revises: 45c8bccac8e0
Create Date: 2026-10-21 22:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1170143ab2d3"
down_revision: str | Sequence[str] | None = "45c8bccac8e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("place_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("loose", sa.Text(), server_default="[]", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("place_items", schema=None) as batch_op:
        batch_op.drop_column("loose")
