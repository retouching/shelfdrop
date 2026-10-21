"""Exceptions of the access tokens."""


class TokenRefusedError(Exception):
    """No token with this secret, or one expired or revoked: it never says which."""


class TokenThrottledError(Exception):
    """More than 60 requests in a minute with this token."""


class TokenNotFoundError(Exception):
    """No token to revoke with this id, or one revoked already."""
