"""Audit trail serializers (read) and query validation."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.audit.models import AuditLog
from apps.core.pagination import PageQuerySerializer
from apps.core.serializers import UTCDateTimeField
from apps.users.refs import actor_ref


class AuditEntrySerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """``{id, at, actor, action, target?}`` – ``target`` is omitted when there is none, exactly
    like the frontend's optional ``target?: string``."""

    id = serializers.SerializerMethodField()
    at = UTCDateTimeField()
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = ("id", "at", "actor", "action", "target")

    def get_id(self, entry: AuditLog) -> str:
        return str(entry.pk)

    def get_actor(self, entry: AuditLog) -> dict[str, Any] | None:
        if entry.actor_role is None:
            return None
        # ``actor_id`` survives only while the account does; fall back to a stable placeholder so
        # the entry keeps rendering for an actor whose account was removed (demo reset).
        return actor_ref(
            entry.actor_id or "00000000-0000-0000-0000-000000000000",
            entry.actor_role,
            entry.actor_name_fa or "",
            entry.actor_name_en or "",
        )

    def to_representation(self, instance: AuditLog) -> dict[str, Any]:
        data: dict[str, Any] = super().to_representation(instance)
        if not data.get("target"):
            data.pop("target", None)
        return data


class AuditQuerySerializer(PageQuerySerializer):
    default_page_size = 15
    max_page_size = 100
