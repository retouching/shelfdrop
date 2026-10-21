"""A fake repository of the access tokens, in memory."""

from dataclasses import replace
from typing import Literal, override

from shelfdrop.tokens.repository import TokenRepository
from shelfdrop.tokens.types import AccessToken, Scope, StoredToken
from tests.unit.support import no_session


class FakeTokenRepository(TokenRepository):
    def __init__(self) -> None:
        super().__init__(no_session())
        self.rows: dict[int, tuple[str, AccessToken, int | None]] = {}
        self.audit: list[tuple[int, str, str, str]] = []
        self.commits = 0

    @override
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
        token = AccessToken(
            id=len(self.rows) + 1,
            name=name,
            scope=scope,
            created_by=created_by,
            created_at=created_at,
            expires_at=expires_at,
            last_used_at=None,
        )
        self.rows[token.id] = (token_hash, token, None)
        return token

    @override
    def list_active(self) -> list[AccessToken]:
        return [t for _, t, revoked in reversed(self.rows.values()) if revoked is None]

    @override
    def read(self, token_hash: str, now: int) -> StoredToken | None:
        for kept, token, revoked in self.rows.values():
            alive = token.expires_at is None or token.expires_at > now
            if kept == token_hash and revoked is None and alive:
                return StoredToken(
                    id=token.id,
                    name=token.name,
                    scope=token.scope,
                    expires_at=token.expires_at,
                    last_used_at=token.last_used_at,
                )
        return None

    @override
    def mark_used(self, token_id: int, now: int) -> None:
        kept, token, revoked = self.rows[token_id]
        self.rows[token_id] = (kept, replace(token, last_used_at=now), revoked)

    @override
    def revoke(self, token_id: int, now: int) -> AccessToken | None:
        found = self.rows.get(token_id)
        if found is None or found[2] is not None:
            return None
        self.rows[token_id] = (found[0], found[1], now)
        return found[1]

    @override
    def add_audit(
        self, at: int, actor: str, action: Literal["created", "revoked"], token_id: int
    ) -> None:
        self.audit.append((at, actor, action, f"token.{token_id}"))

    @override
    def commit(self) -> None:
        self.commits += 1
