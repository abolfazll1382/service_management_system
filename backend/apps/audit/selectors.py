"""Reading the audit trail."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.audit.models import AuditLog


class AuditSelector:
    @staticmethod
    def newest_first() -> QuerySet[AuditLog]:
        """All entries, newest first (``id`` is monotonic, so this is stable and index-backed)."""
        return AuditLog.objects.order_by("-id")
