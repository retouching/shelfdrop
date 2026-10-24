"""Request and response schemas of the setup module."""

from pydantic import BaseModel, ConfigDict


class SetupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # The set-up of the first launch is not finished: the API answers 409 `setup_required`
    # but on the set-up, the session and the settings.
    needed: bool
    # The internal account exists (the first step is done).
    account: bool
