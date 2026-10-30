"""Vocabulary of the audit app."""

from __future__ import annotations

from django.db import models


class AuditAction(models.TextChoices):
    """snake_case, no dots: each value doubles as a segment of the frontend's dictionary key
    ``staff.audit.actions.<action>``."""

    AUTH_REGISTER = "auth_register"
    AUTH_LOGIN = "auth_login"
    AUTH_LOGIN_FAILED = "auth_login_failed"
    REQUEST_CREATED = "request_created"
    REQUEST_STATUS_CHANGED = "request_status_changed"
    REQUEST_ASSIGNED = "request_assigned"
    REQUEST_MESSAGE_ADDED = "request_message_added"
    STAFF_CREATED = "staff_created"
    STAFF_UPDATED = "staff_updated"
    SERVICE_PAUSED = "service_paused"
    SERVICE_RESUMED = "service_resumed"
    DEMO_RESET = "demo_reset"
