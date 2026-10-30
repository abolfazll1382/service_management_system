"""Operational endpoints and JSON replacements for Django's HTML error pages."""

from __future__ import annotations

from typing import Any

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ApiErrorCode, error_payload
from apps.core.messages import preferred_language


class HealthSerializer(serializers.Serializer):  # type: ignore[type-arg]
    status = serializers.ChoiceField(choices=["ok", "unavailable"])


class HealthView(APIView):
    """``GET /health/`` – liveness *and* database reachability, for load balancers and probes.

    Deliberately unauthenticated and outside ``/api``. It reveals nothing but
    ``ok``/``unavailable``.
    """

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []
    throttle_classes: list[Any] = []

    @extend_schema(
        tags=["ops"],
        auth=[],
        responses={200: HealthSerializer, 503: HealthSerializer},
        summary="Liveness and database reachability (for probes and load balancers)",
    )
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except DatabaseError:
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})


def _json_error(request: HttpRequest, code: ApiErrorCode, status: int) -> JsonResponse:
    language = preferred_language(request.headers.get("Accept-Language"))
    return JsonResponse(error_payload(code, language), status=status)


def bad_request(request: HttpRequest, exception: Exception) -> JsonResponse:
    return _json_error(request, ApiErrorCode.VALIDATION, 400)


def permission_denied(request: HttpRequest, exception: Exception) -> JsonResponse:
    return _json_error(request, ApiErrorCode.FORBIDDEN, 403)


def not_found(request: HttpRequest, exception: Exception) -> JsonResponse:
    return _json_error(request, ApiErrorCode.NOT_FOUND, 404)


def server_error(request: HttpRequest) -> JsonResponse:
    """Unexpected failure. The contract has one generic code for it (``network``); details are in
    the server log, correlated by the ``X-Request-ID`` response header."""
    return _json_error(request, ApiErrorCode.NETWORK, 500)
