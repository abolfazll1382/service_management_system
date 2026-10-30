"""Reads over requests: the staff work queue, a customer's own list, single requests (with the
timeline already filtered for the viewer) and assignment candidates.

Everything the viewer may *not* see is excluded **in the query** — a customer's timeline is
fetched without internal notes, so there is no response path on which they could leak.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from django.db.models import Count, Prefetch, Q, QuerySet

from apps.core.exceptions import ForbiddenError
from apps.core.ids import parse_uuid
from apps.core.pagination import Page, paginate
from apps.core.persian import normalize_digits
from apps.requests.access import authorize_request_action
from apps.requests.choices import MessageVisibility, RequestStatus, TimelineEventKind
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.users.models import User
from apps.users.policies import (
    Action,
    PolicyResource,
    can,
    can_assign_to,
    visible_departments,
)
from apps.users.selectors import UserSelector

#: Newest activity first; the trailing keys make the order total, so paging never skips or repeats.
_QUEUE_ORDER = ("-updated_at", "-submitted_at", "id")


def _timeline_for(viewer: User) -> Prefetch[str, QuerySet[TimelineEvent], str]:
    """Prefetch a request's events into ``timeline_events`` for ``viewer``.

    Staff and administrators (anyone with console access) see everything for the requests they
    can read at all; a customer is given only events that are public *by construction*.
    """
    events = TimelineEvent.objects.order_by("sequence")
    if not can(viewer, Action.CONSOLE_ACCESS):
        events = events.filter(
            Q(
                kind__in=(
                    TimelineEventKind.SUBMITTED,
                    TimelineEventKind.STATUS_CHANGED,
                    TimelineEventKind.ASSIGNED,
                )
            )
            | Q(kind=TimelineEventKind.MESSAGE, visibility=MessageVisibility.PUBLIC)
        )
    return Prefetch("events", queryset=events, to_attr="timeline_events")


def _with_timeline(queryset: QuerySet[ServiceRequest], viewer: User) -> QuerySet[ServiceRequest]:
    return queryset.select_related("assignee").prefetch_related(_timeline_for(viewer))


class RequestSelector:
    @staticmethod
    def fetch_for_viewer(viewer: User, request_id: UUID) -> ServiceRequest | None:
        """Load one request shaped for ``viewer`` *without* an access check — only for use right
        after a mutation that has already authorised the viewer."""
        return _with_timeline(ServiceRequest.objects.filter(pk=request_id), viewer).first()

    @staticmethod
    def get_authorized(
        viewer: User, request_id: str, action: Action = Action.REQUEST_READ
    ) -> ServiceRequest:
        """One request for whoever may read it (its owner, its department's staff, an admin).

        A malformed id is just "no such request" (``not_found``), like an unknown one.
        """
        parsed = parse_uuid(request_id)
        request = (
            _with_timeline(ServiceRequest.objects.filter(pk=parsed), viewer).first()
            if parsed is not None
            else None
        )
        return authorize_request_action(viewer, request, action)

    @staticmethod
    def mine(customer: User) -> QuerySet[ServiceRequest]:
        """A customer's own requests, newest activity first (customers only; the view guards it)."""
        owned = ServiceRequest.objects.filter(customer=customer).order_by(*_QUEUE_ORDER)
        return _with_timeline(owned, customer)


@dataclass(frozen=True, slots=True)
class QueueFilters:
    """Everything is optional. ``search`` matches tracking code, applicant name, national ID or
    phone (digits may be typed in Persian or Arabic-Indic script)."""

    status: str | None = None
    department_id: str | None = None
    assignment: Literal["mine", "unassigned"] | None = None
    search: str = ""
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True, slots=True)
class RequestPage:
    page: Page[ServiceRequest]
    #: Per-status totals for the same filters EXCEPT ``status`` itself, so the status tabs can show
    #: how many requests each would list.
    counts: dict[str, int]


class RequestQueueSelector:
    @staticmethod
    def page(actor: User, filters: QueueFilters) -> RequestPage:
        """The work queue.

        The department scope is applied **first**, from the caller's grants, so no filter a client
        sends can widen it: a staff member's queue simply never contains another department's
        request, and asking for one by ``departmentId`` is refused outright.
        """
        if not can(actor, Action.CONSOLE_ACCESS):
            raise ForbiddenError()
        visible = visible_departments(actor)
        if filters.department_id is not None and filters.department_id not in visible:
            raise ForbiddenError()
        scope = [filters.department_id] if filters.department_id else list(visible)

        queryset = ServiceRequest.objects.filter(department__in=scope)
        if filters.assignment == "mine":
            queryset = queryset.filter(assignee_id=actor.pk)
        elif filters.assignment == "unassigned":
            queryset = queryset.filter(assignee__isnull=True)

        needle = normalize_digits(filters.search.strip())
        if needle:
            queryset = queryset.filter(
                Q(tracking_code__icontains=needle)
                | Q(customer_national_id__icontains=needle)
                | Q(customer_phone__icontains=needle)
                | Q(customer_full_name__icontains=needle)
            )

        totals = dict(queryset.order_by().values_list("status").annotate(total=Count("pk")))
        counts = {status.value: totals.get(status.value, 0) for status in RequestStatus}

        if filters.status is not None:
            queryset = queryset.filter(status=filters.status)
        ordered = _with_timeline(queryset, actor).order_by(*_QUEUE_ORDER)
        page = paginate(ordered, page=filters.page, page_size=filters.page_size)
        return RequestPage(page=page, counts=counts)


class AssignmentSelector:
    @staticmethod
    def assignable_staff(actor: User, department_id: str) -> list[User]:
        """Who the caller could assign this department's requests to: themselves, or — for an
        administrator — any active staff member of the department."""
        if not can(actor, Action.REQUEST_ASSIGN, PolicyResource(department_id=department_id)):
            raise ForbiddenError()
        return [
            candidate
            for candidate in UserSelector.active_staff_of_department(department_id)
            if can_assign_to(actor, candidate, department_id)
        ]
