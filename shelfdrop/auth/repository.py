"""SessionRepository: the sessions of the accounts signed in."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from shelfdrop.auth.types import Account, StoredSession
from shelfdrop.db.models import LoginSession


class SessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read(self, token_hash: str, now: int) -> StoredSession | None:
        """The session of this fingerprint, unless it expired."""
        row = self.session.scalar(
            select(LoginSession).where(
                LoginSession.token_hash == token_hash, LoginSession.expires_at > now
            )
        )
        if row is None:
            return None
        return StoredSession(
            token_hash=row.token_hash,
            account=Account(user_id=row.user_id, username=row.username),
            jellyfin_token=row.jellyfin_token,
            device_id=row.device_id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            checked_at=row.checked_at,
        )

    def add(self, stored: StoredSession) -> None:
        self.session.add(
            LoginSession(
                token_hash=stored.token_hash,
                user_id=stored.account.user_id,
                username=stored.account.username,
                jellyfin_token=stored.jellyfin_token,
                device_id=stored.device_id,
                created_at=stored.created_at,
                expires_at=stored.expires_at,
                checked_at=stored.checked_at,
            )
        )

    def mark_checked(self, token_hash: str, now: int) -> None:
        row = self.session.get(LoginSession, token_hash)
        if row is not None:
            row.checked_at = now

    def remove(self, token_hash: str) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash))

    def remove_account_sessions(self, user_id: str, *, keep: str) -> None:
        """Every session of the account `user_id` but the one of the fingerprint `keep`."""
        self.session.execute(
            delete(LoginSession).where(
                LoginSession.user_id == user_id, LoginSession.token_hash != keep
            )
        )

    def remove_expired(self, now: int) -> None:
        self.session.execute(delete(LoginSession).where(LoginSession.expires_at <= now))

    def commit(self) -> None:
        self.session.commit()
