"""Exceptions of the clients of the services."""


class ServiceError(Exception):
    """A service did not answer, or answered an error; the message names a status or a class,
    `status` is the HTTP status of an answer."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

    @property
    def refused(self) -> bool:
        """The service refused the credentials (401 or 403)."""
        return self.status in (401, 403)


class ServiceNotConfiguredError(ServiceError):
    """No address, or no key, in the settings."""
