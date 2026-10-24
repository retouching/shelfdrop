"""The rule of the set-up of the first launch. Pure: no I/O."""

from shelfdrop.accounts.types import StoredAccount


def setup_needed(account: StoredAccount | None, jellyfin_url: str | None) -> bool:
    """Without an internal account, the set-up is needed until Jellyfin has an address: an
    installation signed in through Jellyfin alone never sees it. With one, until its set-up
    is finished; an account created from the settings is finished at its creation."""
    if account is None:
        return jellyfin_url is None
    return account.setup_finished_at is None
