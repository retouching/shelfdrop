"""Types of the access tokens: a token as the page lists it, a token just created with its
secret, and the holder of a token accepted (ADR 0020)."""

from dataclasses import dataclass
from typing import Literal

type Scope = Literal["read", "write"]
"""`read`: the reads of the API and the tools of reading of the MCP server; `write`: those and
the downloads, the files placed, the waiting searches."""


@dataclass(frozen=True, kw_only=True)
class AccessToken:
    id: int
    name: str
    scope: Scope
    created_by: str
    created_at: int
    expires_at: int | None
    last_used_at: int | None


@dataclass(frozen=True, kw_only=True)
class NewToken:
    token: AccessToken
    secret: str
    """Given once, at the creation: the database keeps its SHA-256 alone."""


@dataclass(frozen=True, kw_only=True)
class StoredToken:
    """A token as it is kept: what the check of a request needs."""

    id: int
    name: str
    scope: Scope
    expires_at: int | None
    last_used_at: int | None
