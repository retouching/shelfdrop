"""Request and response schemas of the session module."""

from pydantic import BaseModel, ConfigDict, Field


class SignInBody(BaseModel):
    # Sent to Jellyfin alone; a 422 never repeats them.
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1024)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The name of the account in Jellyfin.
    username: str
