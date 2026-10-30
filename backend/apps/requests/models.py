"""Service requests and their timeline (schema only).

Design notes
------------
* A request keeps a **snapshot** of who filed it (name, national ID, phone): it keeps showing the
  applicant as they were even if the profile changes later, and the work-queue search runs on these
  denormalised columns without joining ``users``.
* The **timeline** is an append-only list of events. Each event carries its own copy of the actor's
  role and names (customers cannot read the users table), a per-request ``sequence`` that defines
  the order, and *exactly the columns its kind needs* — a CHECK constraint enforces the shape.
* Indexes are shaped by the queries: the staff queue (department, status, newest first), the
  "my work" filter (assignee, status), the customer's list, and trigram indexes behind the
  ``icontains`` search box.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import CheckConstraint, F, Func, Q, UniqueConstraint, Value
from django.db.models.functions import Length
from django.db.models.lookups import Exact, GreaterThanOrEqual, LessThanOrEqual
from django.utils import timezone

from apps.core.choices import Department
from apps.core.models import UUIDModel
from apps.requests.choices import MessageVisibility, RequestStatus, TimelineEventKind
from apps.users.choices import UserRole


def _length_between(column: str, lowest: int, highest: int) -> Q:
    """``lowest <= char_length(column) <= highest`` (the ``__length`` lookup is not available for
    ``TextField``, so the function is applied explicitly)."""
    return Q(GreaterThanOrEqual(Length(column), lowest), LessThanOrEqual(Length(column), highest))


def _details_is_object() -> Exact:
    return Exact(
        Func(F("details"), function="jsonb_typeof", output_field=models.CharField()),
        Value("object"),
    )


class ServiceRequest(UUIDModel):
    #: 10-digit reference number shown to the customer. Unique (DB-enforced).
    tracking_code = models.CharField(max_length=10)

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="service_requests",
        db_index=False,  # ``request_customer_idx`` below starts with the customer
    )
    # Identity as it was when the request was filed.
    customer_full_name = models.CharField(max_length=100)
    customer_national_id = models.CharField(max_length=10)
    customer_phone = models.CharField(max_length=11)

    #: Denormalised from the service at filing time; the unit of staff authorisation.
    department = models.CharField(max_length=32, choices=Department.choices)
    service = models.ForeignKey(
        "catalog.Service", on_delete=models.PROTECT, related_name="requests"
    )
    description = models.TextField()
    #: Values for the service's own fields, validated against its definitions (see catalog.fields).
    details = models.JSONField(default=dict)

    status = models.CharField(
        max_length=24, choices=RequestStatus.choices, default=RequestStatus.PENDING_REVIEW
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_requests",
        db_index=False,  # ``request_assignee_status_idx`` below starts with the assignee
    )

    submitted_at = models.DateTimeField(default=timezone.now)
    #: Last activity (every timeline event moves it); the queue sorts on it.
    updated_at = models.DateTimeField(default=timezone.now)

    if TYPE_CHECKING:
        #: Not a column: ``RequestSelector`` prefetches the events *this viewer may see* into it.
        timeline_events: list[TimelineEvent]

    class Meta:
        constraints = [
            UniqueConstraint(fields=["tracking_code"], name="request_tracking_code_unique"),
            CheckConstraint(
                condition=Q(tracking_code__regex=r"^[0-9]{10}$"),
                name="request_tracking_code_format",
            ),
            CheckConstraint(
                condition=Q(status__in=RequestStatus.values), name="request_status_known"
            ),
            CheckConstraint(
                condition=Q(department__in=Department.values), name="request_department_known"
            ),
            CheckConstraint(
                condition=_length_between("description", 10, 1000),
                name="request_description_length",
            ),
            CheckConstraint(condition=_details_is_object(), name="request_details_is_object"),
            CheckConstraint(
                condition=Q(customer_national_id__regex=r"^[0-9]{10}$")
                & Q(customer_phone__regex=r"^09[0-9]{9}$"),
                name="request_customer_snapshot_format",
            ),
        ]
        indexes = [
            # The staff queue: one department's requests by status, newest activity first.
            models.Index(fields=["department", "status", "-updated_at"], name="request_queue_idx"),
            # "Assigned to me", and finding open work to release when a staff member changes.
            models.Index(fields=["assignee", "status"], name="request_assignee_status_idx"),
            # A customer's own list.
            models.Index(fields=["customer", "-updated_at"], name="request_customer_idx"),
            # Administrators' cross-department queue.
            models.Index(fields=["-updated_at"], name="request_updated_idx"),
            # Trigram indexes: make the queue's `icontains` search index-assisted.
            GinIndex(
                fields=["tracking_code"], name="request_code_trgm", opclasses=["gin_trgm_ops"]
            ),
            GinIndex(
                fields=["customer_national_id"],
                name="request_natid_trgm",
                opclasses=["gin_trgm_ops"],
            ),
            GinIndex(
                fields=["customer_phone"], name="request_phone_trgm", opclasses=["gin_trgm_ops"]
            ),
            GinIndex(
                fields=["customer_full_name"],
                name="request_name_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"request:{self.tracking_code}"


def _all_null(*columns: str) -> Q:
    return Q(**{f"{column}__isnull": True for column in columns})


def _none_null(*columns: str) -> Q:
    return Q(**{f"{column}__isnull": False for column in columns})


_ASSIGNEE = ("assignee_role", "assignee_name_fa", "assignee_name_en")
_STATUS = ("from_status", "to_status")
_MESSAGE = ("visibility", "body")


class TimelineEvent(UUIDModel):
    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="events",
        db_index=False,  # the (request, sequence) unique constraint below starts with the request
    )
    #: 0-based position within the request; defines the order (``at`` can tie).
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=16, choices=TimelineEventKind.choices)
    at = models.DateTimeField()

    # Who did it — frozen at the time (see apps.users.refs).
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    actor_role = models.CharField(max_length=16, choices=UserRole.choices)
    actor_name_fa = models.CharField(max_length=100)
    actor_name_en = models.CharField(max_length=100)

    # kind = status_changed
    from_status = models.CharField(
        max_length=24, choices=RequestStatus.choices, null=True, blank=True
    )
    to_status = models.CharField(
        max_length=24, choices=RequestStatus.choices, null=True, blank=True
    )

    # kind = assigned (assignee NULL means "unassigned")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    assignee_role = models.CharField(max_length=16, choices=UserRole.choices, null=True, blank=True)
    assignee_name_fa = models.CharField(max_length=100, null=True, blank=True)
    assignee_name_en = models.CharField(max_length=100, null=True, blank=True)

    # kind = message
    visibility = models.CharField(
        max_length=10, choices=MessageVisibility.choices, null=True, blank=True
    )
    body = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            UniqueConstraint(
                fields=["request", "sequence"], name="timeline_request_sequence_unique"
            ),
            CheckConstraint(
                condition=Q(kind__in=TimelineEventKind.values), name="timeline_kind_known"
            ),
            # Each kind fills exactly its own columns and leaves the others NULL.
            CheckConstraint(
                condition=(
                    (
                        Q(kind=TimelineEventKind.SUBMITTED)
                        & _all_null("assignee", *_ASSIGNEE, *_STATUS, *_MESSAGE)
                    )
                    | (
                        Q(kind=TimelineEventKind.STATUS_CHANGED)
                        & _none_null(*_STATUS)
                        & ~Q(from_status=F("to_status"))
                        & _all_null("assignee", *_ASSIGNEE, *_MESSAGE)
                    )
                    | (
                        Q(kind=TimelineEventKind.ASSIGNED)
                        & _all_null(*_STATUS, *_MESSAGE)
                        & (_all_null("assignee", *_ASSIGNEE) | _none_null("assignee", *_ASSIGNEE))
                    )
                    | (
                        Q(kind=TimelineEventKind.MESSAGE)
                        & _none_null(*_MESSAGE)
                        & _length_between("body", 1, 1000)
                        & _all_null("assignee", *_ASSIGNEE, *_STATUS)
                    )
                ),
                name="timeline_shape_matches_kind",
            ),
        ]

    def __str__(self) -> str:
        return f"event:{self.request_id}:{self.sequence}:{self.kind}"
