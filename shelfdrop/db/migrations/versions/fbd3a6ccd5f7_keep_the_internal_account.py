"""Keep the internal account.

The account of shelfdrop itself (ADR 0023): one row at most, its name, the scrypt of its
password, when it was created and its password changed, and when the set-up of the first
launch it opened was finished. An installation signed in through Jellyfin has none.

Revision ID: fbd3a6ccd5f7
Revises: 06e04acd80d1
Create Date: 2026-10-24 08:54:15.425907

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fbd3a6ccd5f7"
down_revision: str | Sequence[str] | None = "06e04acd80d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "internal_account",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("password_changed_at", sa.Integer(), nullable=False),
        sa.Column("setup_finished_at", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_internal_account")),
    )


def downgrade() -> None:
    op.drop_table("internal_account")
