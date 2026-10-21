"""AuditEntry: who changed which setting, and when; never a value."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class AuditEntry(Base):
    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Unix seconds.
    at: Mapped[int] = mapped_column(Integer, index=True)
    # The account, or "environment" for a value imported at start.
    actor: Mapped[str] = mapped_column(String(255))
    # "changed", "replaced", "cleared", "imported" (shelfdrop.settings.types.AuditAction).
    action: Mapped[str] = mapped_column(String(20))
    # The key of the setting or of the secret.
    target: Mapped[str] = mapped_column(String(100))
