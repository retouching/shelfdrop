"""shelfdrop.accounts.rules: when the set-up of the first launch is needed."""

import pytest

from shelfdrop.accounts.rules import setup_needed
from shelfdrop.accounts.types import StoredAccount


def account(finished_at: int | None) -> StoredAccount:
    return StoredAccount(
        username="admin",
        password_hash="scrypt$...",
        created_at=1,
        password_changed_at=1,
        setup_finished_at=finished_at,
    )


@pytest.mark.parametrize(
    ("stored", "jellyfin_url", "needed"),
    [
        # A new installation: nothing yet.
        (None, None, True),
        # An installation signed in through Jellyfin alone (its address saved or imported).
        (None, "http://jellyfin:8096", False),
        # The first step done: the set-up stays open, even once Jellyfin is saved.
        (account(None), None, True),
        (account(None), "http://jellyfin:8096", True),
        # Finished: by the set-up, or an account created from the settings.
        (account(5), "http://jellyfin:8096", False),
        (account(5), None, False),
    ],
)
def test_the_set_up_is_needed(
    stored: StoredAccount | None, jellyfin_url: str | None, needed: bool
) -> None:
    assert setup_needed(stored, jellyfin_url) is needed
