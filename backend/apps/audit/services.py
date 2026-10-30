"""Writing to the audit trail."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.utils import timezone

from apps.audit.choices import AuditAction
from apps.audit.models import AuditLog
from apps.users.refs import snapshot_of

if TYPE_CHECKING:
    from apps.users.models import User

_TARGET_MAX_LENGTH = 64


def clean_target(target: str) -> str:
    """Make a caller-influenced identifier safe to store and display: drop control characters
    (log injection, NUL) and cap the length."""
    return "".join(ch for ch in target if ch.isprintable())[:_TARGET_MAX_LENGTH]


class AuditService:
    @staticmethod
    def record(
        *,
        actor: User | None,
        action: AuditAction,
        target: str = "",
        at: datetime | None = None,
    ) -> AuditLog:
        """Append one entry.

        Callers invoke this *inside* the transaction of the change being recorded, so the entry
        commits or rolls back together with it. The one deliberate exception is a failed sign-in,
        which is recorded outside any transaction that is about to be abandoned.
        """
        snap = snapshot_of(actor) if actor is not None else None
        return AuditLog.objects.create(
            at=at or timezone.now(),
            actor=actor,
            actor_role=snap.role if snap else None,
            actor_name_fa=snap.name_fa if snap else None,
            actor_name_en=snap.name_en if snap else None,
            action=action,
            target=clean_target(target),
        )
