"""Keep the links of the series to their works.

The work a series of the page Jellyfin was linked to by hand, in the place of the first work the
sources find under its name: its id and its name, by the id of the folder of the series.

Revision ID: d28ca6c7c890
Revises: b1c027fe08ea
Create Date: 2026-10-24 14:43:51.088249

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d28ca6c7c890"
down_revision: str | Sequence[str] | None = "b1c027fe08ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "series_links",
        sa.Column("series_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("work_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("series_id", name=op.f("pk_series_links")),
    )


def downgrade() -> None:
    op.drop_table("series_links")
