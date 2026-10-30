"""Vocabulary of the requests app."""

from __future__ import annotations

from django.db import models


class RequestStatus(models.TextChoices):
    """Deliberately ordinary administrative statuses; the allowed moves between them live in
    ``apps.requests.workflow`` so the API and the tests share one definition."""

    PENDING_REVIEW = "pending_review"
    IN_PROGRESS = "in_progress"
    NEEDS_CORRECTION = "needs_correction"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class MessageVisibility(models.TextChoices):
    """``internal`` notes are staff-only; the server never sends them to a customer."""

    PUBLIC = "public"
    INTERNAL = "internal"


class TimelineEventKind(models.TextChoices):
    SUBMITTED = "submitted"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    MESSAGE = "message"
