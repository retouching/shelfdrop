"""Exceptions of the settings."""


class InvalidSettingsError(Exception):
    """Settings or secrets the catalog does not know, or values it refuses; `keys` lists them."""

    def __init__(self, keys: list[str]) -> None:
        super().__init__("invalid settings")
        self.keys = keys


class SecretUnreadableError(Exception):
    """A sealed secret the key of now cannot open: SHELFDROP_SECRET_KEY changed."""
