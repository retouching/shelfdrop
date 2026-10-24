"""AccountRepository: the internal account, one row at most."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shelfdrop.accounts.types import StoredAccount
from shelfdrop.db.models import InternalAccount

# The key of the one row.
ACCOUNT_ID = 1


class AccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read(self) -> StoredAccount | None:
        row = self.session.scalar(select(InternalAccount).where(InternalAccount.id == ACCOUNT_ID))
        if row is None:
            return None
        return StoredAccount(
            username=row.username,
            password_hash=row.password_hash,
            created_at=row.created_at,
            password_changed_at=row.password_changed_at,
            setup_finished_at=row.setup_finished_at,
        )

    def create(self, account: StoredAccount) -> bool:
        """Adds the account and commits; False when one exists already (the first one wins)."""
        self.session.add(
            InternalAccount(
                id=ACCOUNT_ID,
                username=account.username,
                password_hash=account.password_hash,
                created_at=account.created_at,
                password_changed_at=account.password_changed_at,
                setup_finished_at=account.setup_finished_at,
            )
        )
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return False
        return True

    def save_password(self, password_hash: str, now: int) -> None:
        row = self.session.get(InternalAccount, ACCOUNT_ID)
        if row is not None:
            row.password_hash = password_hash
            row.password_changed_at = now

    def finish_setup(self, now: int) -> None:
        row = self.session.get(InternalAccount, ACCOUNT_ID)
        if row is not None and row.setup_finished_at is None:
            row.setup_finished_at = now

    def commit(self) -> None:
        self.session.commit()
