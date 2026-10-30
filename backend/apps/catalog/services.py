"""Catalogue mutations and the validation of request details against a service definition."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.choices import AuditAction
from apps.audit.services import AuditService
from apps.catalog.definitions import SERVICE_DEFINITIONS, ServiceDefinition
from apps.catalog.fields import clean_details, validate_field_definitions
from apps.catalog.models import Service
from apps.core.exceptions import ForbiddenError, NotFoundError, ValidationFailedError
from apps.users.locking import lock_active_actor
from apps.users.models import User
from apps.users.policies import Action, can


@dataclass(frozen=True, slots=True)
class SyncReport:
    created: int
    updated: int


class CatalogService:
    @staticmethod
    def set_active(*, actor: User, service_id: str, is_active: bool) -> Service:
        """Pause or resume a service (admin only). Always audited, even when nothing changes."""
        if not can(actor, Action.SERVICE_MANAGE):
            raise ForbiddenError()
        now = timezone.now()
        with transaction.atomic():
            admin, _ = lock_active_actor(actor)
            if not can(admin, Action.SERVICE_MANAGE):
                raise ForbiddenError()
            service = Service.objects.select_for_update(no_key=True).filter(pk=service_id).first()
            if service is None:
                raise NotFoundError()
            service.is_active = is_active
            service.updated_at = now
            service.save(update_fields=["is_active", "updated_at"])
            AuditService.record(
                actor=admin,
                action=AuditAction.SERVICE_RESUMED if is_active else AuditAction.SERVICE_PAUSED,
                target=service.pk,
                at=now,
            )
        return service

    @staticmethod
    def clean_details(service: Service, raw_details: Mapping[str, Any]) -> dict[str, Any]:
        """Validate a request's ``details`` against ``service``'s field definitions.

        Unknown keys are dropped and empty optional values omitted; any problem raises a
        ``validation`` error whose ``errors`` map ``details.<key>`` to message keys.
        """
        cleaned, errors = clean_details(service.field_definitions, raw_details)
        if errors:
            raise ValidationFailedError(errors)
        return cleaned

    @staticmethod
    @transaction.atomic
    def sync_definitions(
        definitions: Iterable[ServiceDefinition] = SERVICE_DEFINITIONS,
        *,
        reset_availability: bool = False,
    ) -> SyncReport:
        """Make the database match ``definitions`` (idempotent; the code is only initial content).

        Existing services keep their availability switch unless ``reset_availability`` is set (the
        demo reset). Services present in the database but not in ``definitions`` are left alone:
        requests may reference them.
        """
        created = updated = 0
        for position, definition in enumerate(definitions):
            validate_field_definitions(list(definition.fields))
            values: dict[str, Any] = {
                "department": definition.department,
                "title": definition.title,
                "summary": definition.summary,
                "description": definition.description,
                "requirements": list(definition.requirements),
                "eta_days": definition.eta_days,
                "field_definitions": list(definition.fields),
                "position": position,
            }
            if reset_availability:
                values["is_active"] = True
            _, was_created = Service.objects.update_or_create(pk=definition.id, defaults=values)
            created += was_created
            updated += not was_created
        return SyncReport(created=created, updated=updated)
