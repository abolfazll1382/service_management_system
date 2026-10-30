"""Request serializers: input validation (write) and wire shapes (read).

Read shapes are the frontend's ``ServiceRequest`` / ``TimelineEvent`` exactly (camelCase; ISO-8601
UTC timestamps). They are always rendered *for a viewer*: the serializer needs
``context={"viewer": user}`` and refuses to run without it, so there is no way to render a request
"for nobody in particular" and leak an internal note by accident.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from apps.core import messages as m
from apps.core.choices import Department
from apps.core.pagination import PageQuerySerializer
from apps.core.serializers import (
    ActorRefSerializer,
    KeyedCharField,
    KeyedChoiceField,
    KeyedDictField,
    UTCDateTimeField,
)
from apps.requests.access import resource_of
from apps.requests.choices import MessageVisibility, RequestStatus, TimelineEventKind
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.requests.workflow import requires_note
from apps.users.models import User
from apps.users.policies import Action, can
from apps.users.refs import actor_ref, actor_ref_of

# --- Input -----------------------------------------------------------------------------------


class CreateRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """File a request. Everything else (customer, department, status, assignee, tracking code) is
    decided by the server; extra keys in the body are ignored."""

    serviceId = KeyedCharField(
        error_key=m.V_REQUIRED, max_length=64, error_messages={"max_length": m.V_INVALID}
    )
    description = KeyedCharField(
        error_key=m.V_DESCRIPTION_MIN,  # empty/too short
        min_length=10,
        max_length=1000,
        error_messages={"max_length": m.V_DESCRIPTION_MAX, "invalid": m.V_REQUIRED},
    )
    #: Only the chosen service's field definitions can judge the values: see ``CatalogService``.
    details = KeyedDictField()


class TransitionSerializer(serializers.Serializer):  # type: ignore[type-arg]
    to = KeyedChoiceField(RequestStatus.choices, error_key=m.V_INVALID)
    #: Shown to the applicant as a public message; *required* to reject or ask for corrections.
    note = KeyedCharField(
        required=False,
        allow_blank=True,
        error_key=m.V_INVALID,
        max_length=1000,
        error_messages={"max_length": m.V_DESCRIPTION_MAX},
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if requires_note(attrs["to"]) and not attrs.get("note"):
            raise serializers.ValidationError({"note": [m.V_NOTE_REQUIRED]})
        return attrs


class AssignSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """``{"assigneeId": "<staff id>"}`` to assign, ``{"assigneeId": null}`` to release. The key
    itself is mandatory, so an empty body never silently un-assigns anything."""

    assigneeId = KeyedCharField(allow_null=True, error_key=m.V_INVALID, max_length=64)


class MessageSerializer(serializers.Serializer):  # type: ignore[type-arg]
    body = KeyedCharField(
        error_key=m.V_REQUIRED, max_length=1000, error_messages={"max_length": m.V_DESCRIPTION_MAX}
    )
    visibility = KeyedChoiceField(MessageVisibility.choices, error_key=m.V_INVALID)


class QueueQuerySerializer(PageQuerySerializer):
    """``?status=&departmentId=&assignment=&search=&page=&pageSize=`` (all optional; an empty value
    counts as absent)."""

    default_page_size = 10
    max_page_size = 50

    status = KeyedChoiceField(RequestStatus.choices, required=False)
    departmentId = KeyedChoiceField(Department.choices, required=False)
    assignment = KeyedChoiceField([("mine", "mine"), ("unassigned", "unassigned")], required=False)
    search = KeyedCharField(required=False, allow_blank=True, error_key=m.V_INVALID, max_length=100)


class AssignableStaffQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    departmentId = KeyedChoiceField(Department.choices)


# --- Output: the timeline --------------------------------------------------------------------


class _EventBase(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField(read_only=True)
    at = UTCDateTimeField(read_only=True)
    actor = serializers.SerializerMethodField()

    @extend_schema_field(ActorRefSerializer)
    def get_actor(self, event: TimelineEvent) -> dict[str, Any]:
        # The actor as they were at the time (customers cannot read the users table).
        return actor_ref(event.actor_id, event.actor_role, event.actor_name_fa, event.actor_name_en)


def _kind(kind: TimelineEventKind) -> serializers.ChoiceField:
    return serializers.ChoiceField(choices=[kind.value], read_only=True)


class SubmittedEventSerializer(_EventBase):
    kind = _kind(TimelineEventKind.SUBMITTED)


class StatusChangedEventSerializer(_EventBase):
    kind = _kind(TimelineEventKind.STATUS_CHANGED)
    to = serializers.ChoiceField(choices=RequestStatus.choices, source="to_status", read_only=True)

    def get_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = super().get_fields()
        # ``from`` is a Python keyword, so it cannot be declared as a class attribute.
        fields["from"] = serializers.ChoiceField(
            choices=RequestStatus.choices, source="from_status", read_only=True
        )
        return fields


class AssignedEventSerializer(_EventBase):
    kind = _kind(TimelineEventKind.ASSIGNED)
    assignee = serializers.SerializerMethodField()

    @extend_schema_field(ActorRefSerializer(allow_null=True))
    def get_assignee(self, event: TimelineEvent) -> dict[str, Any] | None:
        if event.assignee_id is None or event.assignee_role is None:
            return None  # "unassigned"
        return actor_ref(
            event.assignee_id,
            event.assignee_role,
            event.assignee_name_fa or "",
            event.assignee_name_en or "",
        )


class MessageEventSerializer(_EventBase):
    kind = _kind(TimelineEventKind.MESSAGE)
    visibility = serializers.ChoiceField(choices=MessageVisibility.choices, read_only=True)
    body = serializers.CharField(read_only=True)


_EVENT_SERIALIZERS: dict[str, type[serializers.Serializer]] = {  # type: ignore[type-arg]
    TimelineEventKind.SUBMITTED: SubmittedEventSerializer,
    TimelineEventKind.STATUS_CHANGED: StatusChangedEventSerializer,
    TimelineEventKind.ASSIGNED: AssignedEventSerializer,
    TimelineEventKind.MESSAGE: MessageEventSerializer,
}

#: For OpenAPI only: ``TimelineEvent`` is a union discriminated by ``kind``.
TimelineEventSchema = PolymorphicProxySerializer(
    component_name="TimelineEvent",
    serializers={
        "submitted": SubmittedEventSerializer,
        "status_changed": StatusChangedEventSerializer,
        "assigned": AssignedEventSerializer,
        "message": MessageEventSerializer,
    },
    resource_type_field_name="kind",
    many=True,
)


def _is_internal_note(event: TimelineEvent) -> bool:
    return (
        event.kind == TimelineEventKind.MESSAGE and event.visibility == MessageVisibility.INTERNAL
    )


@extend_schema_field(TimelineEventSchema)
class TimelineField(serializers.Field):  # type: ignore[type-arg]
    """The request's events, in order, as *this viewer* may see them.

    The selector has already left internal notes out of a customer's query; this applies the policy
    a second time on the way out, so the two layers would both have to fail for one to leak.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(source="*", read_only=True, **kwargs)

    def to_representation(self, value: ServiceRequest) -> list[dict[str, Any]]:
        viewer: User = self.context["viewer"]  # KeyError (a loud 500) rather than a silent leak
        may_read_internal = can(viewer, Action.REQUEST_COMMENT_INTERNAL, resource_of(value))
        return [
            dict(_EVENT_SERIALIZERS[event.kind](event).data)
            for event in value.timeline_events
            if may_read_internal or not _is_internal_note(event)
        ]


# --- Output: the request ---------------------------------------------------------------------


class CustomerSnapshotSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Who filed the request, as they were when they filed it."""

    fullName = serializers.CharField(source="customer_full_name", read_only=True)
    nationalId = serializers.CharField(source="customer_national_id", read_only=True)
    phone = serializers.CharField(source="customer_phone", read_only=True)


class ServiceRequestSerializer(serializers.Serializer):  # type: ignore[type-arg]
    id = serializers.UUIDField(read_only=True)
    #: 10-digit reference number shown to the customer.
    trackingCode = serializers.CharField(source="tracking_code", read_only=True)
    customerId = serializers.UUIDField(source="customer_id", read_only=True)
    customer = CustomerSnapshotSerializer(source="*", read_only=True)
    departmentId = serializers.ChoiceField(
        choices=Department.choices, source="department", read_only=True
    )
    serviceId = serializers.CharField(source="service_id", read_only=True)
    description = serializers.CharField(read_only=True)
    details = serializers.JSONField(read_only=True)
    status = serializers.ChoiceField(choices=RequestStatus.choices, read_only=True)
    assignee = serializers.SerializerMethodField()
    timeline = TimelineField()
    submittedAt = UTCDateTimeField(source="submitted_at", read_only=True)
    updatedAt = UTCDateTimeField(source="updated_at", read_only=True)

    @extend_schema_field(ActorRefSerializer(allow_null=True))
    def get_assignee(self, request: ServiceRequest) -> dict[str, Any] | None:
        return actor_ref_of(request.assignee) if request.assignee is not None else None


class StatusCountsSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Documentation shape of ``counts``: one integer per status, zeros included."""

    pending_review = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    needs_correction = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    closed = serializers.IntegerField()


class RequestPageSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Documentation shape of the work queue's response."""

    items = ServiceRequestSerializer(many=True)
    total = serializers.IntegerField()
    page = serializers.IntegerField()
    pageSize = serializers.IntegerField()
    counts = StatusCountsSerializer()


def request_data(request: ServiceRequest, viewer: User) -> dict[str, Any]:
    """One request, rendered for ``viewer``."""
    data: dict[str, Any] = ServiceRequestSerializer(request, context={"viewer": viewer}).data
    return data


def requests_data(requests: Sequence[ServiceRequest], viewer: User) -> list[dict[str, Any]]:
    """Several requests, rendered for ``viewer``."""
    serializer = ServiceRequestSerializer(requests, many=True, context={"viewer": viewer})
    return list(serializer.data)
