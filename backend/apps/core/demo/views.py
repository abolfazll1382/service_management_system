"""``POST /api/demo/reset/`` (administrators only, and only where the demo tooling is enabled)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.demo.service import DemoService
from apps.core.exceptions import NotFoundError
from apps.users.models import AccessToken
from apps.users.permissions import allows, require_actor
from apps.users.policies import Action


class DemoResetView(APIView):
    permission_classes = [allows(Action.DEMO_RESET)]

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        # Where the feature is off the route does not exist, for everyone — it must not even
        # reveal itself as "admin only" to someone probing a production deployment.
        if not settings.ENABLE_DEMO_RESET:
            raise NotFoundError()
        super().initial(request, *args, **kwargs)

    @extend_schema(
        tags=["demo"],
        request=None,
        responses={204: OpenApiResponse(description="Seed data restored; other sessions ended.")},
        summary="Restore the demo's seed data (administrators; demo deployments only)",
    )
    def post(self, request: Request) -> Response:
        actor = require_actor(request)
        token = request.auth if isinstance(request.auth, AccessToken) else None
        DemoService.reset(actor=actor, keep_token=token)
        return Response(status=status.HTTP_204_NO_CONTENT)
