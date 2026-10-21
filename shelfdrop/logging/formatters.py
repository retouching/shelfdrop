"""Log record formatters."""

import json
import logging
from datetime import UTC, datetime
from typing import Final

# Attributes of every LogRecord plus those added by Formatter.format: never copied as extras.
# `color_message` is uvicorn's ANSI-colored copy of the message; `request_id` has its own key.
NOT_EXTRA: Final = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "color_message",
    "request_id",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line.

    Fields: timestamp (UTC, ISO 8601), level, logger, message, request_id (null outside
    requests), the record's extra fields, then exception (traceback) and stack when present.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, object] = {
            "timestamp": timestamp.isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in vars(record).items():
            if key not in NOT_EXTRA:
                # The fields above win over an extra field with the same name.
                payload.setdefault(key, value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str)
