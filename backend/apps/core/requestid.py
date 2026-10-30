"""The current request's id, for log lines.

Stdlib only, because Django resolves the logging filter during ``django.setup()`` — before the app
registry (and therefore any model or DRF import) is available.
"""

from __future__ import annotations

import logging
import re
from contextvars import ContextVar, Token

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

#: What an incoming ``X-Request-ID`` must look like to be kept (anything else is replaced).
SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")


def set_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def current_request_id() -> str:
    return _request_id.get()


class RequestIDLogFilter(logging.Filter):
    """Adds ``%(request_id)s`` to every log record.

    Django logs 4xx/5xx responses *after* the middleware chain has returned (so the context
    variable is already reset); those records carry the request itself, which the middleware
    tagged with ``request_id``, so the id is recovered from there.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = current_request_id()
        if request_id == "-":
            request_id = str(getattr(getattr(record, "request", None), "request_id", "-"))
        record.request_id = request_id
        return True
