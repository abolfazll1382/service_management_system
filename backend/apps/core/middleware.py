"""Cross-cutting HTTP middleware: request ids and a request-size ceiling."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

from apps.core.exceptions import ApiErrorCode, error_payload
from apps.core.messages import preferred_language
from apps.core.requestid import SAFE_REQUEST_ID, reset_request_id, set_request_id

GetResponse = Callable[[HttpRequest], HttpResponse]


class RequestIDMiddleware:
    """Tag every request/response with an ``X-Request-ID`` (kept if the caller sent a sane one)
    and make it available to log lines via :class:`apps.core.requestid.RequestIDLogFilter`."""

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if SAFE_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]  # for Django's own 4xx logs
        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response["X-Request-ID"] = request_id
        return response


class RequestBodyLimitMiddleware:
    """Refuse bodies larger than ``API_MAX_BODY_BYTES`` before anything reads them.

    Every legitimate payload here is a few hundred bytes. DRF does not apply Django's
    ``DATA_UPLOAD_MAX_MEMORY_SIZE`` to JSON bodies, so without this a multi-gigabyte
    ``Content-Length`` would be read into memory. (A reverse proxy limit is still advised.)
    """

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        raw_length = request.META.get("CONTENT_LENGTH")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                length = -1
            if length < 0 or length > settings.API_MAX_BODY_BYTES:
                language = preferred_language(request.headers.get("Accept-Language"))
                return JsonResponse(
                    error_payload(ApiErrorCode.VALIDATION, language),
                    status=400 if length < 0 else 413,
                )
        return self.get_response(request)
