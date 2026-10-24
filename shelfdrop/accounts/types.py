"""Types of the internal account: the account as it is kept, as the page reads it, and the
state of the set-up of the first launch."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class StoredAccount:
    username: str
    password_hash: str
    """scrypt, with its parameters and its salt (shelfdrop.utils.passwords)."""
    created_at: int
    password_changed_at: int
    setup_finished_at: int | None
    """None while the set-up of the first launch is not finished."""


@dataclass(frozen=True, kw_only=True)
class AccountView:
    """The internal account on the page: never its hash."""

    username: str
    created_at: int
    password_changed_at: int


@dataclass(frozen=True, kw_only=True)
class SetupState:
    needed: bool
    """The set-up of the first launch is not finished: the API answers its routes alone."""
    account: bool
    """The internal account exists."""
