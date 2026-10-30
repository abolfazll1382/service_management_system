"""Mutations of requests: filing, status changes, assignment and messages.

Every public method is one unit of work. It authorises the caller, changes state inside
``transaction.atomic``, appends the timeline events *and* the audit entry in that same transaction
(so history can never disagree with state), and raises a domain error on refusal. Nothing here
builds an HTTP response, and every method returns the request shaped for the caller (internal notes
already removed for customers), so a view cannot forget to do it.

Concurrency
-----------
* Lock order is always **users (by id) → request** (see :mod:`apps.users.locking`); filing locks
  **user → service**. One order everywhere means no two transactions can wait on each other.
* The caller's own account is re-read under its lock and every permission is decided on that
  *fresh* row, so "an administrator just removed this person's access" takes effect on the very
  next write instead of at their next sign-in.
* A lock-free authorisation pass runs first, so someone who may not touch a request can never make
  anybody else wait on its row.
* Each request's timeline has a per-request ``sequence``; it is allocated while the request row is
  locked, which is what makes it gap-free and collision-free.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.choices import AuditAction
from apps.audit.services import AuditService
from apps.catalog.models import Service
from apps.catalog.services import CatalogService
from apps.core import messages as m
from apps.core.db import violated_constraint
from apps.core.exceptions import (
    ForbiddenError,
    InvalidTransitionError,
    NotFoundError,
    RequestClosedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from apps.core.ids import parse_uuid
from apps.core.persian import generate_tracking_code
from apps.requests.access import authorize_request_action
from apps.requests.choices import MessageVisibility, RequestStatus, TimelineEventKind
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.requests.selectors import RequestSelector
from apps.requests.workflow import OPEN_STATUSES, can_transition, is_closed, requires_note
from apps.users.choices import UserRole
from apps.users.locking import lock_active_actor
from apps.users.models import User
from apps.users.policies import Action, can, can_assign_to
from apps.users.refs import snapshot_of

#: 10^10 codes: a collision is vanishingly rare, but the contract is "unique", so retry a few times.
_TRACKING_CODE_ATTEMPTS = 8
_TRACKING_CODE_CONSTRAINT = "request_tracking_code_unique"


@dataclass(frozen=True, slots=True)
class _NewEvent:
    """One timeline event to append (everything but the actor, time and sequence)."""

    kind: TimelineEventKind
    from_status: str | None = None
    to_status: str | None = None
    #: For ``assigned`` events: the new assignee, or ``None`` for "unassigned".
    assignee: User | None = None
    visibility: str | None = None
    body: str | None = None


def _status_changed(from_status: str, to_status: str) -> _NewEvent:
    return _NewEvent(
        kind=TimelineEventKind.STATUS_CHANGED, from_status=from_status, to_status=to_status
    )


def _assigned(assignee: User | None) -> _NewEvent:
    return _NewEvent(kind=TimelineEventKind.ASSIGNED, assignee=assignee)


def _message(body: str, visibility: str) -> _NewEvent:
    return _NewEvent(kind=TimelineEventKind.MESSAGE, visibility=visibility, body=body)


def _build_event(
    request: ServiceRequest, sequence: int, actor: User, at: datetime, new: _NewEvent
) -> TimelineEvent:
    who = snapshot_of(actor)
    assignee = snapshot_of(new.assignee) if new.assignee is not None else None
    return TimelineEvent(
        request=request,
        sequence=sequence,
        kind=new.kind,
        at=at,
        actor=actor,
        actor_role=who.role,
        actor_name_fa=who.name_fa,
        actor_name_en=who.name_en,
        from_status=new.from_status,
        to_status=new.to_status,
        assignee=new.assignee,
        assignee_role=assignee.role if assignee else None,
        assignee_name_fa=assignee.name_fa if assignee else None,
        assignee_name_en=assignee.name_en if assignee else None,
        visibility=new.visibility,
        body=new.body,
    )


def _next_sequences(requests: Sequence[ServiceRequest]) -> dict[UUID, int]:
    """The next free ``sequence`` of each request (callers hold the requests' row locks)."""
    last = dict(
        TimelineEvent.objects.filter(request__in=requests)
        .order_by()
        .values_list("request_id")
        .annotate(last=Max("sequence"))
    )
    return {request.pk: last[request.pk] + 1 if request.pk in last else 0 for request in requests}


def _append_events(
    request: ServiceRequest, actor: User, events: Sequence[_NewEvent], at: datetime
) -> None:
    sequence = _next_sequences([request])[request.pk]
    TimelineEvent.objects.bulk_create(
        [
            _build_event(request, sequence + offset, actor, at, event)
            for offset, event in enumerate(events)
        ]
    )


def _peek(request_id: UUID | None) -> ServiceRequest | None:
    """The request, read *without* a lock (for the cheap first authorisation pass)."""
    return ServiceRequest.objects.filter(pk=request_id).first() if request_id else None


def _lock(request_id: UUID | None) -> ServiceRequest | None:
    """The request, locked ``FOR NO KEY UPDATE``. Plain query on purpose: no joins, so the lock
    never touches (or fails on) the nullable ``assignee`` side."""
    if request_id is None:
        return None
    return ServiceRequest.objects.select_for_update(no_key=True).filter(pk=request_id).first()


def _shaped(viewer: User, request_id: UUID) -> ServiceRequest:
    request = RequestSelector.fetch_for_viewer(viewer, request_id)
    if request is None:  # deleted by a demo reset between commit and read
        raise NotFoundError()
    return request


def _save(request: ServiceRequest, *, at: datetime, fields: Sequence[str]) -> None:
    request.updated_at = at
    request.save(update_fields=[*fields, "updated_at"])


class RequestWorkflowService:
    # --- Customer ----------------------------------------------------------------------------

    @staticmethod
    def create_request(
        *, actor: User, service_id: str, description: str, details: Mapping[str, Any]
    ) -> ServiceRequest:
        """File a request as a customer.

        The department, applicant snapshot, status and (absent) assignee are all decided here;
        nothing the client sends can set them. ``details`` is re-validated against the service's own
        field definitions.
        """
        if not can(actor, Action.REQUEST_CREATE):
            raise ForbiddenError()
        now = timezone.now()
        with transaction.atomic():
            customer, _ = lock_active_actor(actor)
            if not can(customer, Action.REQUEST_CREATE):
                raise ForbiddenError()

            # Locked so that "pause this service" is a real barrier: once the administrator's change
            # has committed, no further request is accepted (a filing in flight at that moment
            # simply finishes first).
            service = Service.objects.select_for_update(no_key=True).filter(pk=service_id).first()
            if service is None:
                raise NotFoundError()
            if not service.is_active:
                raise ServiceUnavailableError()
            cleaned = CatalogService.clean_details(service, details)

            request = RequestWorkflowService._insert(
                customer=customer, service=service, description=description, details=cleaned, at=now
            )
            _append_events(request, customer, [_NewEvent(kind=TimelineEventKind.SUBMITTED)], now)
            AuditService.record(
                actor=customer,
                action=AuditAction.REQUEST_CREATED,
                target=request.tracking_code,
                at=now,
            )
        return _shaped(customer, request.pk)

    @staticmethod
    def _insert(
        *,
        customer: User,
        service: Service,
        description: str,
        details: dict[str, Any],
        at: datetime,
    ) -> ServiceRequest:
        for _attempt in range(_TRACKING_CODE_ATTEMPTS):
            try:
                with transaction.atomic():  # a savepoint: a collision must not poison the outer one
                    return ServiceRequest.objects.create(
                        tracking_code=generate_tracking_code(),
                        customer=customer,
                        # A snapshot: the request keeps showing who filed it even if the profile
                        # changes later (and the queue search needs no join).
                        customer_full_name=customer.full_name or "",
                        customer_national_id=customer.national_id or "",
                        customer_phone=customer.phone or "",
                        department=service.department,
                        service=service,
                        description=description,
                        details=details,
                        status=RequestStatus.PENDING_REVIEW,
                        assignee=None,
                        submitted_at=at,
                        updated_at=at,
                    )
            except IntegrityError as exc:
                if violated_constraint(exc) != _TRACKING_CODE_CONSTRAINT:
                    raise
        raise RuntimeError("Could not allocate a unique tracking code")  # pragma: no cover

    # --- Staff -------------------------------------------------------------------------------

    @staticmethod
    def transition(
        *, actor: User, request_id: str, to_status: str, note: str | None
    ) -> ServiceRequest:
        """Move a request along the workflow.

        Starting a review (``pending_review → in_progress``) by a staff member who finds the request
        unassigned claims it for them, so two colleagues never both pick it up. A ``note`` is shown
        to the applicant as a public message; rejecting or asking for corrections *requires* one.
        """
        if to_status not in RequestStatus.values:
            raise ValidationFailedError({"to": [m.V_INVALID]})
        if requires_note(to_status) and not note:
            raise ValidationFailedError({"note": [m.V_NOTE_REQUIRED]})

        target = parse_uuid(request_id)
        authorize_request_action(actor, _peek(target), Action.REQUEST_TRANSITION)
        now = timezone.now()
        with transaction.atomic():
            acting, _ = lock_active_actor(actor)
            request = authorize_request_action(acting, _lock(target), Action.REQUEST_TRANSITION)
            if is_closed(request.status):
                raise RequestClosedError()
            if not can_transition(request.status, to_status):
                raise InvalidTransitionError()

            events: list[_NewEvent] = []
            changed = ["status"]
            claims = (
                acting.role == UserRole.STAFF
                and request.status == RequestStatus.PENDING_REVIEW
                and to_status == RequestStatus.IN_PROGRESS
                and request.assignee_id is None
            )
            if claims:
                request.assignee = acting
                changed.append("assignee")
                events.append(_assigned(acting))
            events.append(_status_changed(request.status, to_status))
            if note:
                events.append(_message(note, MessageVisibility.PUBLIC))

            request.status = to_status
            _save(request, at=now, fields=changed)
            _append_events(request, acting, events, now)
            AuditService.record(
                actor=acting,
                action=AuditAction.REQUEST_STATUS_CHANGED,
                target=request.tracking_code,
                at=now,
            )
        return _shaped(acting, request.pk)

    @staticmethod
    def assign(*, actor: User, request_id: str, assignee_id: str | None) -> ServiceRequest:
        """Assign the request to a staff member of its department, or release it (``None``).

        Staff can only claim for themselves; administrators can hand work to any eligible
        colleague. Re-assigning to the current assignee changes nothing and records nothing.
        """
        target = parse_uuid(request_id)
        authorize_request_action(actor, _peek(target), Action.REQUEST_ASSIGN)
        wanted = parse_uuid(assignee_id) if assignee_id is not None else None
        now = timezone.now()
        with transaction.atomic():
            acting, locked = lock_active_actor(actor, wanted)
            request = authorize_request_action(acting, _lock(target), Action.REQUEST_ASSIGN)
            if is_closed(request.status):
                raise RequestClosedError()

            assignee: User | None = None
            if assignee_id is not None:
                assignee = locked.get(wanted) if wanted is not None else None
                if assignee is None:
                    raise NotFoundError()
            if not can_assign_to(acting, assignee, request.department):
                raise ForbiddenError()

            if (assignee.pk if assignee else None) != request.assignee_id:
                request.assignee = assignee
                _save(request, at=now, fields=["assignee"])
                _append_events(request, acting, [_assigned(assignee)], now)
                AuditService.record(
                    actor=acting,
                    action=AuditAction.REQUEST_ASSIGNED,
                    target=request.tracking_code,
                    at=now,
                )
        return _shaped(acting, request.pk)

    # --- Both sides --------------------------------------------------------------------------

    @staticmethod
    def add_message(*, actor: User, request_id: str, body: str, visibility: str) -> ServiceRequest:
        """Post a message on a request. ``internal`` notes are staff-only.

        An applicant answering a correction request hands the ball back to staff: the server moves
        the request to ``in_progress`` as the consequence of an action the applicant *is* allowed to
        take (it is recorded as their action; they still cannot change a status themselves).
        """
        if visibility not in MessageVisibility.values:
            raise ValidationFailedError({"visibility": [m.V_INVALID]})
        action = (
            Action.REQUEST_COMMENT_INTERNAL
            if visibility == MessageVisibility.INTERNAL
            else Action.REQUEST_COMMENT
        )

        target = parse_uuid(request_id)
        authorize_request_action(actor, _peek(target), action)
        now = timezone.now()
        with transaction.atomic():
            acting, _ = lock_active_actor(actor)
            request = authorize_request_action(acting, _lock(target), action)
            if is_closed(request.status):
                raise RequestClosedError()

            events = [_message(body, visibility)]
            changed: list[str] = []
            if (
                acting.role == UserRole.CUSTOMER
                and request.status == RequestStatus.NEEDS_CORRECTION
            ):
                events.append(_status_changed(request.status, RequestStatus.IN_PROGRESS))
                request.status = RequestStatus.IN_PROGRESS
                changed.append("status")

            _save(request, at=now, fields=changed)
            _append_events(request, acting, events, now)
            AuditService.record(
                actor=acting,
                action=AuditAction.REQUEST_MESSAGE_ADDED,
                target=request.tracking_code,
                at=now,
            )
        return _shaped(acting, request.pk)

    # --- Used by team management -------------------------------------------------------------

    @staticmethod
    def release_open_work_of(*, staff: User, by: User, at: datetime) -> int:
        """Un-assign the open requests of ``staff`` that they can no longer touch.

        "Can no longer touch" means the account was switched off, or the request's department is
        no longer one of theirs. Closed requests keep their assignee (it is history). Returns how
        many requests were released.

        Must run inside the caller's transaction, after ``staff`` (already saved with its new
        state) and ``by`` were locked: the lock order stays users → requests.
        """
        stranded = ServiceRequest.objects.select_for_update(no_key=True).filter(
            assignee=staff, status__in=OPEN_STATUSES
        )
        if staff.is_active:
            stranded = stranded.exclude(department__in=staff.department_ids)
        requests = list(stranded.order_by("pk"))
        if not requests:
            return 0

        sequences = _next_sequences(requests)
        events = [
            _build_event(request, sequences[request.pk], by, at, _assigned(None))
            for request in requests
        ]
        TimelineEvent.objects.bulk_create(events)
        ServiceRequest.objects.filter(pk__in=[request.pk for request in requests]).update(
            assignee=None, updated_at=at
        )
        return len(requests)
