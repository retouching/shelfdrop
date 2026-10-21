"""Keep the events of the journal.

The events of shelfdrop (a send, a placement, a sign-in...), their batch, what their message
says and its picture, and the state of their message on Discord.

Revision ID: a250a56263cc
Revises: e88f18e15668
Create Date: 2026-10-21 20:23:45.715909

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a250a56263cc"
down_revision: str | Sequence[str] | None = "e88f18e15668"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("group_key", sa.String(length=300), nullable=False),
        sa.Column("facts", sa.Text(), nullable=False),
        sa.Column("cover", sa.LargeBinary(), nullable=True),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_events_state"), ["state"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_events_state"))
    op.drop_table("events")
