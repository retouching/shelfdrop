"""Keep the access tokens.

The access tokens of the API and of the MCP server (plan section 3 quater): their name, the
SHA-256 of their secret, their scope, who created them and when, their expiry, their last use
and their revocation.

Revision ID: 06e04acd80d1
Revises: cd0744c2d266
Create Date: 2026-10-22 01:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "06e04acd80d1"
down_revision: str | Sequence[str] | None = "cd0744c2d266"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=10), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_api_tokens_token_hash")),
    )
    with op.batch_alter_table("api_tokens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_api_tokens_revoked_at"), ["revoked_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("api_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_api_tokens_revoked_at"))
    op.drop_table("api_tokens")
