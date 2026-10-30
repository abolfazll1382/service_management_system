"""The API error contract.

Every non-2xx response has exactly this shape (the frontend's ``ApiError`` mirrors it)::

    {"code": "validation", "detail": "<sentence in the caller's language>",
     "errors": {"fieldName": ["validation.some.key"], "details.amount": ["validation.number.min"]}}

* ``code`` is one of :class:`ApiErrorCode` – the stable, machine-readable part.
* ``detail`` is a human sentence, English by default and Persian for ``Accept-Language: fa``.
* ``errors`` is always present (empty unless the failure is about specific fields). Nested
  serializer errors are flattened to dotted paths; each message is a frontend dictionary key.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, ClassVar

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework.response import Response
from rest_framework.views import set_rollback

from apps.core.http import WWW_AUTHENTICATE
from apps.core.messages import (
    DEFAULT_LANGUAGE,
    V_INVALID,
    VALIDATION_KEYS,
    Language,
    error_text,
    preferred_language,
)

logger = logging.getLogger(__name__)


class ApiErrorCode(StrEnum):
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VALIDATION = "validation"
    INVALID_CREDENTIALS = "invalid_credentials"
    NATIONAL_ID_TAKEN = "national_id_taken"
    PHONE_TAKEN = "phone_taken"
    USERNAME_TAKEN = "username_taken"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INVALID_TRANSITION = "invalid_transition"
    REQUEST_CLOSED = "request_closed"
    NETWORK = "network"


class ApplicationError(drf.APIException):
    """Base class of every *expected* failure raised by services and policies.

    Subclasses pin the machine-readable code and the HTTP status; the handler turns them into the
    contract above. Services raise these; they never build responses themselves.
    """

    error_code: ClassVar[ApiErrorCode]

    def __init__(self, errors: Mapping[str, Sequence[str]] | None = None) -> None:
        self.field_errors: dict[str, list[str]] = {
            field: list(messages) for field, messages in (errors or {}).items()
        }
        super().__init__(detail=self.error_code.value, code=self.error_code.value)


class UnauthenticatedError(ApplicationError):
    status_code = 401
    error_code = ApiErrorCode.UNAUTHENTICATED


class ForbiddenError(ApplicationError):
    status_code = 403
    error_code = ApiErrorCode.FORBIDDEN


class NotFoundError(ApplicationError):
    status_code = 404
    error_code = ApiErrorCode.NOT_FOUND


class ValidationFailedError(ApplicationError):
    status_code = 400
    error_code = ApiErrorCode.VALIDATION


class InvalidCredentialsError(ApplicationError):
    status_code = 401
    error_code = ApiErrorCode.INVALID_CREDENTIALS


class NationalIdTakenError(ApplicationError):
    status_code = 409
    error_code = ApiErrorCode.NATIONAL_ID_TAKEN


class PhoneTakenError(ApplicationError):
    status_code = 409
    error_code = ApiErrorCode.PHONE_TAKEN


class UsernameTakenError(ApplicationError):
    status_code = 409
    error_code = ApiErrorCode.USERNAME_TAKEN


class ServiceUnavailableError(ApplicationError):
    status_code = 409
    error_code = ApiErrorCode.SERVICE_UNAVAILABLE


class InvalidTransitionError(ApplicationError):
    status_code = 409
    error_code = ApiErrorCode.INVALID_TRANSITION


class RequestClosedError(ApplicationError):
    status_code = 409
    error_code = ApiErrorCode.REQUEST_CLOSED


# --- Building the response -------------------------------------------------------------------


def error_payload(
    code: ApiErrorCode,
    language: Language = DEFAULT_LANGUAGE,
    errors: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """The JSON body of an error response."""
    return {
        "code": code.value,
        "detail": error_text(code.value, language),
        "errors": {field: list(messages) for field, messages in (errors or {}).items()},
    }


def _as_key(message: object) -> str:
    """Only dictionary keys may leave the API; anything else (e.g. a stock DRF sentence) becomes
    the generic fallback so no English text or internal wording leaks into ``errors``."""
    text = str(message)
    return text if text in VALIDATION_KEYS else V_INVALID


def flatten_validation_errors(detail: Any, prefix: str = "") -> dict[str, list[str]]:
    """Flatten DRF's nested error structure into ``{"dotted.path": ["validation.key", ...]}``."""
    flat: dict[str, list[str]] = {}

    def add(path: str, messages: list[str]) -> None:
        bucket = flat.setdefault(path or "non_field_errors", [])
        bucket.extend(message for message in messages if message not in bucket)

    if isinstance(detail, Mapping):
        for key, value in detail.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            for path, messages in flatten_validation_errors(value, child).items():
                add(path, messages)
    elif isinstance(detail, list | tuple):
        if all(not isinstance(item, Mapping | list | tuple) for item in detail):
            add(prefix, [_as_key(item) for item in detail])
        else:  # a list of child serializers' errors (many=True): index them
            for index, item in enumerate(detail):
                child = f"{prefix}.{index}" if prefix else str(index)
                for path, messages in flatten_validation_errors(item, child).items():
                    add(path, messages)
    else:
        add(prefix, [_as_key(detail)])
    return flat


def _language_of(context: Mapping[str, Any]) -> Language:
    request = context.get("request")
    header = getattr(request, "headers", {}).get("Accept-Language") if request else None
    return preferred_language(header)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """DRF ``EXCEPTION_HANDLER``: translate every expected failure into the contract.

    Anything unexpected returns ``None``, which makes DRF re-raise so Django logs the traceback
    and ``apps.core.views.server_error`` answers with the contract's ``network`` code.
    """
    language = _language_of(context)
    headers: dict[str, str] = {}
    errors: Mapping[str, Sequence[str]] = {}

    if isinstance(exc, Http404):
        exc = drf.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf.PermissionDenied()

    if isinstance(exc, ApplicationError):
        code, status, errors = exc.error_code, exc.status_code, exc.field_errors
    elif isinstance(exc, drf.ValidationError):
        code, status = ApiErrorCode.VALIDATION, 400
        errors = flatten_validation_errors(exc.detail)
    elif isinstance(exc, drf.NotAuthenticated | drf.AuthenticationFailed):
        code, status = ApiErrorCode.UNAUTHENTICATED, 401
    elif isinstance(exc, drf.PermissionDenied):
        code, status = ApiErrorCode.FORBIDDEN, 403
    elif isinstance(exc, drf.NotFound | drf.MethodNotAllowed):
        # No route/verb is an unknown resource as far as the contract is concerned; the HTTP
        # status (404 / 405) still tells proxies and tools the precise story.
        code, status = ApiErrorCode.NOT_FOUND, exc.status_code
    elif isinstance(exc, drf.ParseError | drf.UnsupportedMediaType | drf.NotAcceptable):
        code, status = ApiErrorCode.VALIDATION, exc.status_code
    elif isinstance(exc, drf.Throttled):
        code, status = ApiErrorCode.NETWORK, 429
        wait: float | None = getattr(exc, "wait", None)  # set by DRF; absent from the type stubs
        if wait is not None:
            headers["Retry-After"] = str(max(1, math.ceil(wait)))
    else:
        return None

    if status == 401:
        headers["WWW-Authenticate"] = WWW_AUTHENTICATE

    set_rollback()
    return Response(error_payload(code, language, errors), status=status, headers=headers)
