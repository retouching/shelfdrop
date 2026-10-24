"""Keep the categories of the trackers.

The categories each indexer of Prowlarr gives (read again with the trackers), and those chosen
for each kind. The trackers saved keep no choice: they search the default categories, as before,
and their categories come at the next read of Prowlarr.

Revision ID: 7841e402f749
Revises: 06e04acd80d1
Create Date: 2026-10-24 08:51:53.199115

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7841e402f749"
down_revision: str | Sequence[str] | None = "06e04acd80d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("trackers", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("available_categories", sa.Text(), server_default="[]", nullable=False)
        )
        batch_op.add_column(sa.Column("chosen_categories", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trackers", schema=None) as batch_op:
        batch_op.drop_column("chosen_categories")
        batch_op.drop_column("available_categories")
