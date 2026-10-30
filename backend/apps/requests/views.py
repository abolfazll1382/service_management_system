"""``/api/requests/…``: the thin HTTP layer for requests.

Each view: authenticate → coarse role permission → validate input with a *write* serializer → call
one service or selector → render with a *read* serializer. No business rule lives here.

Which door a caller may use is decided here only coarsely ("is this a console user?"). Whether
*this* caller may touch *that* request is decided object by object in the service/selector, which
also chooses between ``not_found`` (a customer probing someone else's request) and ``forbidden``.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ActorRefSerializer, validate_input
from apps.requests.selectors import (
    AssignmentSelector,
    QueueFilters,
    RequestQueueSelector,
    RequestSelector,
)
from apps.requests.serializers import (
    AssignableStaffQuerySerializer,
    AssignSerializer,
    CreateRequestSerializer,
    MessageSerializer,
    QueueQuerySerializer,
    RequestPageSerializer,
    ServiceRequestSerializer,
    TransitionSerializer,
    request_data,
    requests_data,
)
from apps.requests.services import RequestWorkflowService
from apps.users.permissions import IsCustomer, allows, require_actor
from apps.users.policies import Action
from apps.users.refs import actor_ref_of


class RequestCollectionView(APIView):
    """``POST /api/requests/`` – file a request (customers only)."""

    permission_classes = [allows(Action.REQUEST_CREATE)]

    @extend_schema(
        tags=["requests"],
        request=CreateRequestSerializer,
        responses={201: ServiceRequestSerializer},
        summary="File a request (customers only)",
    )
    def post(self, request: Request) -> Response:
        data = validate_input(CreateRequestSerializer, request.data)
        customer = require_actor(request)
        created = RequestWorkflowService.create_request(
            actor=customer,
            service_id=data["serviceId"],
            description=data["description"],
            details=data["details"],
        )
        return Response(request_data(created, customer), status=status.HTTP_201_CREATED)


class MyRequestsView(APIView):
    """``GET /api/requests/mine/`` – the caller's own requests, newest activity first."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=["requests"],
        responses={200: ServiceRequestSerializer(many=True)},
        summary="The signed-in customer's own requests",
    )
    def get(self, request: Request) -> Response:
        customer = require_actor(request)
        return Response(requests_data(list(RequestSelector.mine(customer)), customer))


class QueueView(APIView):
    """``GET /api/requests/queue/`` – the work queue, scoped to the caller's departments."""

    permission_classes = [allows(Action.CONSOLE_ACCESS)]

    @extend_schema(
        tags=["requests"],
        parameters=[QueueQuerySerializer],
        responses={200: RequestPageSerializer},
        summary="Work queue with per-status counts (staff and administrators)",
    )
    def get(self, request: Request) -> Response:
        query = validate_input(QueueQuerySerializer, request.query_params)
        actor = require_actor(request)
        result = RequestQueueSelector.page(
            actor,
            QueueFilters(
                status=query.get("status"),
                department_id=query.get("departmentId"),
                assignment=query.get("assignment"),
                search=query.get("search", ""),
                page=query["page"],
                page_size=query["pageSize"],
            ),
        )
        return Response(
            result.page.envelope(requests_data(result.page.items, actor), counts=result.counts)
        )


class AssignableStaffView(APIView):
    """``GET /api/requests/assignable-staff/?departmentId=`` – who the caller could assign to."""

    permission_classes = [allows(Action.CONSOLE_ACCESS)]

    @extend_schema(
        tags=["requests"],
        parameters=[AssignableStaffQuerySerializer],
        responses={200: ActorRefSerializer(many=True)},
        summary="Staff the caller may assign this department's requests to",
    )
    def get(self, request: Request) -> Response:
        query = validate_input(AssignableStaffQuerySerializer, request.query_params)
        candidates = AssignmentSelector.assignable_staff(
            require_actor(request), query["departmentId"]
        )
        return Response([actor_ref_of(candidate) for candidate in candidates])


class RequestDetailView(APIView):
    """``GET /api/requests/<id>/`` – one request, for whoever may read it."""

    @extend_schema(
        tags=["requests"],
        responses={200: ServiceRequestSerializer},
        summary="One request (its owner, its department's staff, or an administrator)",
    )
    def get(self, request: Request, request_id: str) -> Response:
        viewer = require_actor(request)
        return Response(request_data(RequestSelector.get_authorized(viewer, request_id), viewer))


class TransitionView(APIView):
    """``POST /api/requests/<id>/transition/`` – change the status."""

    @extend_schema(
        tags=["requests"],
        request=TransitionSerializer,
        responses={200: ServiceRequestSerializer},
        summary="Change a request's status (staff of its department, administrators)",
    )
    def post(self, request: Request, request_id: str) -> Response:
        data = validate_input(TransitionSerializer, request.data)
        actor = require_actor(request)
        updated = RequestWorkflowService.transition(
            actor=actor,
            request_id=request_id,
            to_status=data["to"],
            note=data.get("note") or None,
        )
        return Response(request_data(updated, actor))


class AssignView(APIView):
    """``POST /api/requests/<id>/assign/`` – claim, hand over or release."""

    @extend_schema(
        tags=["requests"],
        request=AssignSerializer,
        responses={200: ServiceRequestSerializer},
        summary="Assign a request to a staff member, or release it",
    )
    def post(self, request: Request, request_id: str) -> Response:
        data = validate_input(AssignSerializer, request.data)
        actor = require_actor(request)
        updated = RequestWorkflowService.assign(
            actor=actor, request_id=request_id, assignee_id=data["assigneeId"]
        )
        return Response(request_data(updated, actor))


class MessageCreateView(APIView):
    """``POST /api/requests/<id>/messages/`` – add a public message or an internal note."""

    @extend_schema(
        tags=["requests"],
        request=MessageSerializer,
        responses={201: ServiceRequestSerializer},
        summary="Post a message (internal notes are staff-only)",
    )
    def post(self, request: Request, request_id: str) -> Response:
        data = validate_input(MessageSerializer, request.data)
        actor = require_actor(request)
        updated = RequestWorkflowService.add_message(
            actor=actor, request_id=request_id, body=data["body"], visibility=data["visibility"]
        )
        return Response(request_data(updated, actor), status=status.HTTP_201_CREATED)
