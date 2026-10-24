"""Request and response models of the access tokens."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from shelfdrop.tokens.types import Scope


class TokenCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"name": "Agent", "scope": "write", "days": None}]}
    )

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    scope: Scope
    days: Literal[30, 90, 365] | None = Field(
        description="How long the token lasts; null: without end."
    )


class TokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope: Scope
    created_by: str
    created_at: int
    expires_at: int | None
    last_used_at: int | None


class TokenCreated(BaseModel):
    token: TokenRead
    secret: str = Field(description="Shown once: the database keeps its SHA-256 alone.")


class TokensRead(BaseModel):
    tokens: list[TokenRead]
