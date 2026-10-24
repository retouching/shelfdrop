"""Response models of the logs."""

from typing import Any

from pydantic import BaseModel, Field


class LogEntryRead(BaseModel):
    timestamp: str = Field(description="UTC, ISO 8601, to the millisecond.")
    level: str
    logger: str
    message: str
    request_id: str | None
    fields: dict[str, Any] = Field(
        description="The other fields of the record: its extra fields, `exception`, `stack`."
    )


class LogsRead(BaseModel):
    entries: list[LogEntryRead] = Field(description="The newest first.")
    next: str | None = Field(
        description="The `before` of the older entries; null: there are no more."
    )
