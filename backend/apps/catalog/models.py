"""The service catalogue (schema only).

A service describes its own extra form fields as *data* (``field_definitions``): the frontend
renders them and the backend validates a request's ``details`` against the very same definition,
so adding a service never means writing a new form component or a second validator.
"""

from __future__ import annotations

from django.db import models
from django.db.models import CheckConstraint, F, Func, Q, Value
from django.db.models.lookups import Exact

from apps.catalog.fields import validate_field_definitions
from apps.core.choices import Department
from apps.core.models import TimeStampedModel


def _json_is(column: str, json_type: str) -> Exact:
    """``jsonb_typeof(column) = '<type>'`` as a constraint expression."""
    return Exact(
        Func(F(column), function="jsonb_typeof", output_field=models.CharField()),
        Value(json_type),
    )


class Service(TimeStampedModel):
    #: Stable slug, e.g. ``personal-loan``. It is the public identifier (``serviceId``).
    id = models.SlugField(primary_key=True, max_length=64)
    department = models.CharField(max_length=32, choices=Department.choices)

    # Localized text: ``{"fa": "...", "en": "..."}``.
    title = models.JSONField()
    summary = models.JSONField()
    description = models.JSONField()
    #: What an applicant should have ready: a list of ``{"fa", "en"}`` objects.
    requirements = models.JSONField(default=list)
    #: Typical processing time in days, shown to set expectations.
    eta_days = models.PositiveSmallIntegerField()
    #: List of field definitions (``kind`` = text | number | select); see ``apps.catalog.fields``.
    field_definitions = models.JSONField(default=list, validators=[validate_field_definitions])

    #: The admin-controlled availability switch ("accepting requests").
    is_active = models.BooleanField(default=True)
    #: Display order in the catalogue.
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            CheckConstraint(
                condition=Q(department__in=Department.values), name="service_department_known"
            ),
            CheckConstraint(condition=Q(eta_days__gte=1), name="service_eta_positive"),
            CheckConstraint(
                condition=(
                    _json_is("title", "object")
                    & _json_is("summary", "object")
                    & _json_is("description", "object")
                    & Q(title__has_keys=["fa", "en"])
                    & Q(summary__has_keys=["fa", "en"])
                    & Q(description__has_keys=["fa", "en"])
                ),
                name="service_texts_localized",
            ),
            CheckConstraint(
                condition=_json_is("requirements", "array")
                & _json_is("field_definitions", "array"),
                name="service_lists_are_arrays",
            ),
        ]
        indexes = [
            models.Index(fields=["department", "position"], name="service_department_pos_idx"),
        ]

    def __str__(self) -> str:
        return str(self.pk)
