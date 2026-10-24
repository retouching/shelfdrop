"""Request and response schemas of the account module: the internal account. A password is
never in a response, and a 422 never repeats it."""

from pydantic import BaseModel, ConfigDict, Field

# The bounds of the internal account, shared with the set-up.
USERNAME = Field(min_length=1, max_length=64, pattern=r"^\S(.*\S)?$")
PASSWORD = Field(min_length=10, max_length=1024)


class AccountBody(BaseModel):
    # No space at either end.
    username: str = USERNAME
    password: str = PASSWORD


class PasswordBody(BaseModel):
    current: str = Field(min_length=1, max_length=1024)
    new: str = PASSWORD


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    # Unix seconds.
    created_at: int
    password_changed_at: int


class AccountState(BaseModel):
    # null without an internal account.
    account: AccountRead | None
