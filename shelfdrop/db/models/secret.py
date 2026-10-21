"""Secret: a key or a token of a service, sealed (ADR 0012), by its name."""

from sqlalchemy import Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from shelfdrop.db.base import Base


class Secret(Base):
    __tablename__ = "secrets"

    # "prowlarr.api_key"...
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    # The nonce, then the AES-GCM ciphertext and its tag; the key is its associated data.
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    # Unix seconds.
    updated_at: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[str] = mapped_column(String(255))
