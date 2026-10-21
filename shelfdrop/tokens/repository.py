"""TokenRepository: the access tokens, and their lines of the audit."""

from typing import Final, Literal

from pydantic import TypeAdapter
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from shelfdrop.db.models import ApiToken, AuditEntry
from shelfdrop.tokens.types import AccessToken, Scope, StoredToken

SCOPE: Final = TypeAdapter[Scope](Scope)


def access_token(row: ApiToken) -> AccessToken:
    return AccessToken(
        id=row.id,
        name=row.name,
        scope=SCOPE.validate_python(row.scope),
        created_by=row.created_by,
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
    )


class TokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        name: str,
        token_hash: str,
        scope: Scope,
        created_by: str,
        created_at: int,
        expires_at: int | None,
    ) -> AccessToken:
        row = ApiToken(
            name=name,
            token_hash=token_hash,
            scope=scope,
            created_by=created_by,
            created_at=created_at,
            expires_at=expires_at,
            last_used_at=None,
            revoked_at=None,
        )
        self.session.add(row)
        self.session.flush()
        return access_token(row)

    def list_active(self) -> list[AccessToken]:
        """The tokens not revoked, expired ones included, the newest first."""
        rows = self.session.scalars(
            select(ApiToken).where(ApiToken.revoked_at.is_(None)).order_by(ApiToken.id.desc())
        )
        return [access_token(row) for row in rows]

    def read(self, token_hash: str, now: int) -> StoredToken | None:
        """The token of this fingerprint, unless it is revoked or expired."""
        row = self.session.scalar(
            select(ApiToken).where(
                ApiToken.token_hash == token_hash,
                ApiToken.revoked_at.is_(None),
                or_(ApiToken.expires_at.is_(None), ApiToken.expires_at > now),
            )
        )
        if row is None:
            return None
        return StoredToken(
            id=row.id,
            name=row.name,
            scope=SCOPE.validate_python(row.scope),
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
        )

    def mark_used(self, token_id: int, now: int) -> None:
        row = self.session.get(ApiToken, token_id)
        if row is not None:
            row.last_used_at = now

    def revoke(self, token_id: int, now: int) -> AccessToken | None:
        """The token revoked; None when there is none to revoke under this id."""
        row = self.session.get(ApiToken, token_id)
        if row is None or row.revoked_at is not None:
            return None
        row.revoked_at = now
        return access_token(row)

    def add_audit(
        self, at: int, actor: str, action: Literal["created", "revoked"], token_id: int
    ) -> None:
        self.session.add(AuditEntry(at=at, actor=actor, action=action, target=f"token.{token_id}"))

    def commit(self) -> None:
        self.session.commit()
