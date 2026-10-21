"""Exceptions of the sign-in. None says what was wrong with the account: a refusal is a
refusal."""


class LoginRefusedError(Exception):
    """Wrong credentials, or an account that is not an administrator, or disabled."""


class TooManyAttemptsError(Exception):
    """Too many sign-in attempts from this address, or from everywhere."""


class JellyfinUnavailableError(Exception):
    """Jellyfin does not answer, or its address is not set: nobody can sign in."""


class NotSignedInError(Exception):
    """No session, an expired one, or one Jellyfin no longer confirms."""
