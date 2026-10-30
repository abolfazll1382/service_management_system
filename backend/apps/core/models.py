"""Abstract base models.

Models in this project are *schema only*: fields, constraints and indexes. Every state change,
invariant spanning several rows and permission decision lives in ``services.py`` / ``policies.py``.
"""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    """Random UUID primary key: ids are safe to expose and impossible to enumerate."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Creation / modification timestamps.

    These default to ``timezone.now`` rather than ``auto_now*`` on purpose: services stamp a single
    ``at`` per operation (so a row and its timeline event agree to the microsecond) and the demo
    seed needs to reproduce exact historical times.
    """

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
