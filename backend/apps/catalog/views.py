"""``/api/catalog/…``: browsing is public, availability is admin-only."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.selectors import CatalogSelector
from apps.catalog.serializers import ServiceListingSerializer, SetServiceActiveSerializer
from apps.catalog.services import CatalogService
from apps.core.exceptions import NotFoundError
from apps.users.permissions import allows, require_actor
from apps.users.policies import Action


class _PublicView(APIView):
    """Browsing the catalogue needs no account; a token (even a bad one) is not even looked at."""

    authentication_classes: list[Any] = []
    permission_classes = [AllowAny]


class ServiceListView(_PublicView):
    @extend_schema(
        tags=["catalog"],
        responses={200: ServiceListingSerializer(many=True)},
        summary="All services with their availability (public)",
    )
    def get(self, request: Request) -> Response:
        return Response(ServiceListingSerializer(CatalogSelector.listings(), many=True).data)


class ServiceDetailView(_PublicView):
    @extend_schema(
        tags=["catalog"],
        responses={200: ServiceListingSerializer},
        summary="One service (public)",
    )
    def get(self, request: Request, service_id: str) -> Response:
        service = CatalogSelector.get(service_id)
        if service is None:
            raise NotFoundError()
        return Response(ServiceListingSerializer(service).data)


class ServiceActiveView(APIView):
    permission_classes = [allows(Action.SERVICE_MANAGE)]

    @extend_schema(
        tags=["catalog"],
        request=SetServiceActiveSerializer,
        responses={200: ServiceListingSerializer},
        summary="Pause or resume a service (admin only)",
    )
    def patch(self, request: Request, service_id: str) -> Response:
        body = SetServiceActiveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        service = CatalogService.set_active(
            actor=require_actor(request),
            service_id=service_id,
            is_active=body.validated_data["isActive"],
        )
        return Response(ServiceListingSerializer(service).data)
