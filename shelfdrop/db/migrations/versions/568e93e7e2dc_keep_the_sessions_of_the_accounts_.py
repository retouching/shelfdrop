"""Keep the sessions of the accounts signed in.

The fingerprint of the token of each session, its account and the sealed access token of
Jellyfin.

Revision ID: 568e93e7e2dc
Revises: eab842edd711
Create Date: 2026-10-21 17:38:28.655119

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "568e93e7e2dc"
down_revision: str | Sequence[str] | None = "eab842edd711"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("jellyfin_token", sa.LargeBinary(), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_sessions")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_expires_at"), ["expires_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_expires_at"))

    op.drop_table("sessions")
