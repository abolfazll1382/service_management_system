"""Catalogue serializers (read) and the availability toggle (write)."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.models import Service
from apps.core.serializers import LocalizedSerializer, StrictBooleanField


class FieldDefinitionSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Documentation shape of one entry of ``fields`` (``kind`` decides which extras apply)."""

    kind = serializers.ChoiceField(choices=["text", "number", "select"])
    key = serializers.CharField()
    # ``label`` and ``required`` are also attributes of DRF's ``Field``; declared fields are
    # collected (and removed from the class) by the serializer metaclass, so the clash is harmless.
    label = LocalizedSerializer()  # type: ignore[assignment]
    required = serializers.BooleanField()  # type: ignore[assignment]
    maxLength = serializers.IntegerField(required=False, help_text="text only")
    min = serializers.FloatField(required=False, help_text="number only")
    max = serializers.FloatField(required=False, help_text="number only")
    unit = LocalizedSerializer(required=False, help_text="number only")
    options = serializers.ListField(
        child=serializers.DictField(), required=False, help_text="select only: {value, label}"
    )


@extend_schema_field(FieldDefinitionSerializer(many=True))
class FieldDefinitionsField(serializers.JSONField):
    """The stored definitions, passed through untouched (they are already in wire shape)."""


class ServiceListingSerializer(serializers.ModelSerializer):  # type: ignore[type-arg]
    """``Service`` + its availability flag, in the frontend's shape (``ServiceListing``)."""

    departmentId = serializers.CharField(source="department", read_only=True)
    etaDays = serializers.IntegerField(source="eta_days", read_only=True)
    isActive = serializers.BooleanField(source="is_active", read_only=True)
    # ``fields`` is the wire name; like any declared field, the metaclass moves it out of the
    # class, so shadowing ``Serializer.fields`` here is harmless.
    fields = FieldDefinitionsField(source="field_definitions", read_only=True)  # type: ignore[assignment]

    class Meta:
        model = Service
        fields = (
            "id",
            "departmentId",
            "title",
            "summary",
            "description",
            "requirements",
            "etaDays",
            "fields",
            "isActive",
        )
        read_only_fields = fields


class SetServiceActiveSerializer(serializers.Serializer):  # type: ignore[type-arg]
    isActive = StrictBooleanField()
