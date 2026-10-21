"""Logging filters."""

import logging

from shelfdrop.logging.context import request_id_var


class RequestIdFilter(logging.Filter):
    """Adds `request_id` to records emitted while a request is handled; others are left as is."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id is not None:
            record.request_id = request_id
        return True
