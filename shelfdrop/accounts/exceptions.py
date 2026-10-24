"""Exceptions of the internal account and of the set-up."""


class AccountExistsError(Exception):
    """The internal account exists already: there is one at most."""


class AccountMissingError(Exception):
    """No internal account."""


class PasswordRefusedError(Exception):
    """The current password given does not match."""


class SetupDoneError(Exception):
    """The set-up of the first launch is finished, or was never needed."""


class JellyfinNotConnectedError(Exception):
    """The set-up cannot finish: the test of the Jellyfin saved fails."""
