"""The audit trail (schema only). Append-only by convention: nothing in the code base updates or
deletes a row except the demo reset; see the README for database-level hardening options."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone

from apps.audit.choices import AuditAction
from apps.users.choices import UserRole


class AuditLog(models.Model):
    #: Monotonic, so "newest first" is simply ``ORDER BY id DESC`` (cheap, and stable even when
    #: several entries share a timestamp).
    id = models.BigAutoField(primary_key=True)
    at = models.DateTimeField(default=timezone.now)

    # Who did it. ``actor`` is nullable for events with no authenticated actor (a failed login)
    # and SET_NULL so history outlives an account; the snapshot columns keep the name readable
    # either way.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        db_index=False,  # ``audit_actor_recent_idx`` below starts with the actor
    )
    actor_role = models.CharField(max_length=16, choices=UserRole.choices, null=True, blank=True)
    actor_name_fa = models.CharField(max_length=100, null=True, blank=True)
    actor_name_en = models.CharField(max_length=100, null=True, blank=True)

    action = models.CharField(max_length=32, choices=AuditAction.choices)
    #: A language-neutral identifier: tracking code, username, service id or *masked* national ID.
    #: Never message text and never a full national ID.
    target = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [
            CheckConstraint(condition=Q(action__in=AuditAction.values), name="audit_action_known"),
            CheckConstraint(
                condition=(
                    Q(
                        actor_role__isnull=True,
                        actor_name_fa__isnull=True,
                        actor_name_en__isnull=True,
                    )
                    | Q(
                        actor_role__isnull=False,
                        actor_name_fa__isnull=False,
                        actor_name_en__isnull=False,
                    )
                ),
                name="audit_actor_snapshot_complete",
            ),
        ]
        indexes = [
            models.Index(fields=["actor", "-id"], name="audit_actor_recent_idx"),
            models.Index(fields=["action", "-id"], name="audit_action_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"audit:{self.pk}:{self.action}"
