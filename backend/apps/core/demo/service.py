"""Seeding the demo data and resetting it.

Two operations:

* :meth:`DemoService.seed` – *create what is missing* (accounts, services, requests). Idempotent and
  non-destructive, so it is safe to run on every container start.
* :meth:`DemoService.reset` – put everything back to the seed: all requests, history and audit
  entries are replaced, every session except the caller's ends, accounts that are not part of the
  seed are removed (administrators excepted), and seed accounts get their original password,
  departments and availability back.

Both serialise on a PostgreSQL advisory lock, so two replicas starting together (or a reset racing
a seed) queue up instead of colliding.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
from django.db.models import Model
from django.utils import timezone

from apps.audit.choices import AuditAction
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.catalog.models import Service
from apps.catalog.services import CatalogService
from apps.core.demo.seed_data import (
    CREATED_AT,
    DEMO_PASSWORD,
    SEED_REQUESTS,
    SEED_USER_IDS,
    SEED_USERS,
    SeedRequest,
    SeedUser,
    parse_instant,
    seed_id,
)
from apps.core.exceptions import ForbiddenError, UnauthenticatedError
from apps.requests.choices import MessageVisibility, RequestStatus, TimelineEventKind
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.users.choices import UserRole
from apps.users.models import AccessToken, User
from apps.users.policies import Action, can
from apps.users.refs import snapshot_of
from apps.users.services import translate_user_integrity_error

#: ``pg_advisory_xact_lock`` key shared by seeding and resetting.
_ADVISORY_LOCK_KEY = 0x5EED_DA7A

#: Tables a reset rewrites, in the order the rest of the code takes its locks (users first).
_REWRITTEN: tuple[type[Model], ...] = (
    User,
    Service,
    ServiceRequest,
    TimelineEvent,
    AccessToken,
    AuditLog,
)


@dataclass(frozen=True, slots=True)
class SeedReport:
    users_created: int
    requests_created: int
    services_created: int


def _lock_advisory() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_ADVISORY_LOCK_KEY])


def _lock_for_rewrite() -> None:
    """Hold off every other writer until this transaction ends.

    ``LOCK TABLE … IN EXCLUSIVE MODE`` lets plain reads through (so authentication keeps working)
    but waits for in-flight writes and blocks new ones. It cannot deadlock: every transaction that
    writes to several of these tables starts with the ``users`` table, which is the first one
    locked here, so a transaction in the way is always waited for *before* anything is held.
    """
    _lock_advisory()
    names = ", ".join(connection.ops.quote_name(model._meta.db_table) for model in _REWRITTEN)
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {names} IN EXCLUSIVE MODE")


def _user_fields(seed: SeedUser, password_hash: str) -> dict[str, Any]:
    """Every column of the account, so an existing row is restored completely, not patched."""
    return {
        "role": seed.role,
        "is_active": True,
        "password": password_hash,
        "last_login": None,
        "username": seed.username,
        "name_fa": seed.name_fa,
        "name_en": seed.name_en,
        "department_ids": list(seed.department_ids),
        "full_name": seed.full_name,
        "national_id": seed.national_id,
        "phone": seed.phone,
        "postal_code": seed.postal_code,
        "address": seed.address,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def _build_request(
    seed: SeedRequest, users: Mapping[str, User]
) -> tuple[ServiceRequest, list[TimelineEvent]]:
    """Replay the request's story into the row and its timeline, exactly as the services would
    have produced it (``sequence`` 0, 1, 2 …; ``updated_at`` = the last event)."""
    customer = users[seed.customer]
    submitted_at = parse_instant(seed.submitted_at)
    status: str = RequestStatus.PENDING_REVIEW
    assignee: User | None = None
    updated_at = submitted_at
    events: list[TimelineEvent] = []

    def event(actor: User, at: datetime, kind: TimelineEventKind, **columns: Any) -> None:
        sequence = len(events)
        who = snapshot_of(actor)
        events.append(
            TimelineEvent(
                id=seed_id(f"{seed.key}-e{sequence}"),
                request_id=seed.id,
                sequence=sequence,
                kind=kind,
                at=at,
                actor=actor,
                actor_role=who.role,
                actor_name_fa=who.name_fa,
                actor_name_en=who.name_en,
                **columns,
            )
        )

    event(customer, submitted_at, TimelineEventKind.SUBMITTED)
    for step in seed.steps:
        actor = users[step.by]
        at = parse_instant(step.at)
        updated_at = at
        if step.kind == "status":
            if step.to is None:
                raise ValueError(f"{seed.key}: a status step needs a target status")
            event(
                actor, at, TimelineEventKind.STATUS_CHANGED, from_status=status, to_status=step.to
            )
            status = step.to
        elif step.kind == "assign":
            assignee = users[step.to] if step.to else None
            columns: dict[str, Any] = {"assignee": assignee}
            if assignee is not None:
                theirs = snapshot_of(assignee)
                columns |= {
                    "assignee_role": theirs.role,
                    "assignee_name_fa": theirs.name_fa,
                    "assignee_name_en": theirs.name_en,
                }
            event(actor, at, TimelineEventKind.ASSIGNED, **columns)
        else:
            event(
                actor,
                at,
                TimelineEventKind.MESSAGE,
                visibility=MessageVisibility(step.visibility),
                body=step.body,
            )

    request = ServiceRequest(
        id=seed.id,
        tracking_code=seed.tracking_code,
        customer=customer,
        customer_full_name=customer.full_name or "",
        customer_national_id=customer.national_id or "",
        customer_phone=customer.phone or "",
        department=seed.department,
        service_id=seed.service_id,
        description=seed.description,
        details=seed.details,
        status=status,
        assignee=assignee,
        submitted_at=submitted_at,
        updated_at=updated_at,
    )
    return request, events


def _insert_requests(seeds: Sequence[SeedRequest], users: Mapping[str, User]) -> int:
    built = [_build_request(seed, users) for seed in seeds]
    ServiceRequest.objects.bulk_create([request for request, _ in built])
    TimelineEvent.objects.bulk_create([event for _, events in built for event in events])
    return len(built)


class DemoService:
    @staticmethod
    def seed() -> SeedReport:
        """Create the demo accounts, services and requests that do not exist yet.

        Anything that already exists is left exactly as it is (it may have been changed on
        purpose); use :meth:`reset` to restore it. A *different* account that already uses a seed
        username raises ``username_taken`` rather than being overwritten.
        """
        services = CatalogService.sync_definitions()
        try:
            with transaction.atomic():
                _lock_advisory()
                present_users = set(
                    User.objects.filter(pk__in=SEED_USER_IDS).values_list("pk", flat=True)
                )
                created_users = 0
                for seed in SEED_USERS:
                    if seed.id in present_users:
                        continue
                    User.objects.create(
                        pk=seed.id, **_user_fields(seed, make_password(DEMO_PASSWORD))
                    )
                    created_users += 1

                users = {seed.key: User.objects.get(pk=seed.id) for seed in SEED_USERS}
                present_requests = set(
                    ServiceRequest.objects.filter(
                        pk__in=[seed.id for seed in SEED_REQUESTS]
                    ).values_list("pk", flat=True)
                )
                missing = [seed for seed in SEED_REQUESTS if seed.id not in present_requests]
                created_requests = _insert_requests(missing, users)
        except IntegrityError as exc:
            translated = translate_user_integrity_error(exc)
            if translated is None:
                raise
            raise translated from exc
        return SeedReport(
            users_created=created_users,
            requests_created=created_requests,
            services_created=services.created,
        )

    @staticmethod
    def reset(*, actor: User | None, keep_token: AccessToken | None) -> None:
        """Restore the seed. ``actor`` is the administrator who asked (``None`` from the command
        line); ``keep_token`` is the session that stays signed in so that administrator is not
        thrown out of the page they are looking at. Every other session ends."""
        hashes = {seed.key: make_password(DEMO_PASSWORD) for seed in SEED_USERS}  # slow: up front
        now = timezone.now()
        try:
            with transaction.atomic():
                _lock_for_rewrite()
                if actor is not None:
                    fresh = User.objects.filter(pk=actor.pk).first()
                    if fresh is None or not fresh.is_active:
                        raise UnauthenticatedError()
                    if not can(fresh, Action.DEMO_RESET):
                        raise ForbiddenError()

                tokens = AccessToken.objects.all()
                if keep_token is not None:
                    tokens = tokens.exclude(pk=keep_token.pk)
                tokens.delete()
                AuditLog.objects.all().delete()
                TimelineEvent.objects.all().delete()
                ServiceRequest.objects.all().delete()
                # Administrators outside the seed are kept (they run the system); every other
                # account that is not part of the seed goes.
                User.objects.exclude(pk__in=SEED_USER_IDS).exclude(role=UserRole.ADMIN).delete()

                users: dict[str, User] = {}
                for seed in SEED_USERS:
                    users[seed.key], _ = User.objects.update_or_create(
                        pk=seed.id, defaults=_user_fields(seed, hashes[seed.key])
                    )
                CatalogService.sync_definitions(reset_availability=True)
                _insert_requests(SEED_REQUESTS, users)

                acting = User.objects.get(pk=actor.pk) if actor is not None else None
                AuditService.record(actor=acting, action=AuditAction.DEMO_RESET, at=now)
        except IntegrityError as exc:
            translated = translate_user_integrity_error(exc)
            if translated is None:
                raise
            raise translated from exc
