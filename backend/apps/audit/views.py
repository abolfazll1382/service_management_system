"""``GET /api/audit/`` (administrators only)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.selectors import AuditSelector
from apps.audit.serializers import AuditEntrySerializer, AuditQuerySerializer
from apps.core.pagination import paginate
from apps.core.serializers import validate_input
from apps.users.permissions import allows
from apps.users.policies import Action


class AuditListView(APIView):
    permission_classes = [allows(Action.AUDIT_READ)]

    @extend_schema(
        tags=["audit"],
        parameters=[AuditQuerySerializer],
        responses={200: AuditEntrySerializer(many=True)},
        summary="Audit trail, newest first (admin only)",
    )
    def get(self, request: Request) -> Response:
        query = validate_input(AuditQuerySerializer, request.query_params)
        page = paginate(
            AuditSelector.newest_first(), page=query["page"], page_size=query["pageSize"]
        )
        return Response(page.envelope(AuditEntrySerializer(page.items, many=True).data))
