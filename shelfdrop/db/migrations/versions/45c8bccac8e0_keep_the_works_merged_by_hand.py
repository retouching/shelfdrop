"""Keep the works merged by hand.

The works the page joined into one (plan section 3, point 9): the keys of their members and the
name on the shelf chosen, applied to every search of their family after.

Revision ID: 45c8bccac8e0
Revises: e24f8ad607d1
Create Date: 2026-10-21 22:23:17.078419

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "45c8bccac8e0"
down_revision: str | Sequence[str] | None = "e24f8ad607d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_merges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("family", sa.String(length=10), nullable=False),
        sa.Column("keys", sa.Text(), nullable=False),
        sa.Column("shelf_name", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_merges")),
    )
    with op.batch_alter_table("work_merges", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_work_merges_family"), ["family"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("work_merges", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_work_merges_family"))

    op.drop_table("work_merges")
