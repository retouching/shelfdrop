"""Keep the secrets and the audit of the settings.

The sealed secrets of the services, who changed which setting, and who changed each setting
last (empty for the rows written before).

Revision ID: eab842edd711
Revises: c7d1d70b5ae2
Create Date: 2026-10-21 17:30:17.465222

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "eab842edd711"
down_revision: str | Sequence[str] | None = "c7d1d70b5ae2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("at", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit")),
    )
    with op.batch_alter_table("audit", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_at"), ["at"], unique=False)

    op.create_table(
        "secrets",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_secrets")),
    )
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("updated_by", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("updated_by")

    op.drop_table("secrets")
    with op.batch_alter_table("audit", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_at"))

    op.drop_table("audit")
