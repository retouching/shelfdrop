"""Create the tables of the release search.

The cache of the answers of Prowlarr, the trackers, the filter rules and the settings.

Revision ID: c7d1d70b5ae2
Revises: e9ad2f300034
Create Date: 2026-10-21 17:00:57.472998

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d1d70b5ae2"
down_revision: str | Sequence[str] | None = "e9ad2f300034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "filter_rules",
        sa.Column("position", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("pattern", sa.String(length=500), nullable=False),
        sa.Column("regex", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("kinds", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("position", name=op.f("pk_filter_rules")),
    )
    op.create_table(
        "release_answers",
        sa.Column("key", sa.String(length=400), nullable=False),
        sa.Column("releases", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_release_answers")),
    )
    with op.batch_alter_table("release_answers", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_release_answers_expires_at"), ["expires_at"], unique=False
        )

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
    )
    op.create_table(
        "trackers",
        sa.Column("indexer_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=True),
        sa.Column("prowlarr_enabled", sa.Boolean(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("auto", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("indexer_id", name=op.f("pk_trackers")),
    )


def downgrade() -> None:
    op.drop_table("trackers")
    op.drop_table("settings")
    with op.batch_alter_table("release_answers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_release_answers_expires_at"))

    op.drop_table("release_answers")
    op.drop_table("filter_rules")
