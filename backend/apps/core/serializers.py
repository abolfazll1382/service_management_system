"""Reusable serializer fields.

Two project-wide conventions live here:

* **Keyed messages.** Every field reports failures as a *frontend dictionary key*
  (``validation.required`` …) instead of DRF's English sentences. The exception handler later
  checks that nothing but known keys leaves the API. Field classes take an ``error_key`` so each
  input names the exact message the UI already has for it.
* **Strictness that matches the Zod schemas.** Strings must be strings (DRF would coerce numbers),
  booleans must be booleans (DRF accepts ``"true"``/``1``), and text is rejected if it contains
  characters PostgreSQL cannot store (NUL, lone surrogates) instead of crashing later with a 500.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from rest_framework import serializers

from apps.core import messages as m
from apps.core.choices import Department
from apps.core.persian import normalize_digits
from apps.core.text import contains_unstorable_characters


def iso_utc(value: datetime) -> str:
    """``2026-10-05T08:30:00.000Z`` – the wire format of every timestamp."""
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class UTCDateTimeField(serializers.DateTimeField):
    """Output-only ISO-8601 UTC timestamp with millisecond precision and a ``Z`` suffix."""

    def to_representation(self, value: Any) -> str:
        return iso_utc(value)


class KeyedMessages:
    """Mixin whose ``default_error_messages`` replace DRF's sentences with dictionary keys.

    DRF merges ``default_error_messages`` along the MRO, so listing this mixin *before* the DRF
    field class makes these win.
    """

    default_error_messages: ClassVar[dict[str, Any]] = {
        "required": m.V_REQUIRED,
        "null": m.V_REQUIRED,
        "blank": m.V_REQUIRED,
        "invalid": m.V_INVALID,
        "max_length": m.V_INVALID,
        "min_length": m.V_INVALID,
        "min_value": m.V_INVALID,
        "max_value": m.V_INVALID,
        "max_string_length": m.V_INVALID,
        "invalid_choice": m.V_INVALID,
        "not_a_list": m.V_INVALID,
        "empty": m.V_INVALID,
    }


class _RejectUnstorableCharacters:
    """Validator: NUL bytes and lone UTF-16 surrogates cannot be stored in PostgreSQL text/jsonb."""

    def __init__(self, key: str) -> None:
        self.key = key

    def __call__(self, value: str) -> None:
        if contains_unstorable_characters(value):
            raise serializers.ValidationError(self.key)


class KeyedCharField(KeyedMessages, serializers.CharField):
    """A strictly-typed string field whose failures all report ``error_key``.

    ``blank_key`` lets a field say "required" for an empty value while using a more specific key
    for other shape problems (a blank message body is *required*, a 1-char name is *fullName*).
    """

    def __init__(
        self,
        *,
        error_key: str = m.V_INVALID,
        blank_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        messages = dict(kwargs.pop("error_messages", {}))
        messages.setdefault("invalid", error_key)
        messages.setdefault("max_length", error_key)
        messages.setdefault("min_length", error_key)
        messages.setdefault("blank", blank_key or error_key)
        super().__init__(error_messages=messages, **kwargs)
        # Replace DRF's two "prohibit" validators (English text) with one that reports the key.
        self.validators = [
            validator
            for validator in self.validators
            if type(validator).__name__
            not in {"ProhibitNullCharactersValidator", "ProhibitSurrogateCharactersValidator"}
        ]
        self.validators.append(_RejectUnstorableCharacters(error_key))

    def to_internal_value(self, data: Any) -> str:
        if not isinstance(data, str):  # DRF would coerce ints/floats; the contract says string
            self.fail("invalid")
        return data.strip() if self.trim_whitespace else data


class DigitsField(KeyedCharField):
    """A string of digits the user may have typed in Persian or Arabic-Indic script.

    Digits are normalised to ASCII *before* any format check or lookup, and surrounding whitespace
    is dropped. (Never use this for passwords.)
    """

    def to_internal_value(self, data: Any) -> str:
        return normalize_digits(super().to_internal_value(data))


class KeyedIntegerField(KeyedMessages, serializers.IntegerField):
    pass


class KeyedChoiceField(KeyedMessages, serializers.ChoiceField):
    def __init__(self, choices: Any, *, error_key: str = m.V_INVALID, **kwargs: Any) -> None:
        messages = dict(kwargs.pop("error_messages", {}))
        messages.setdefault("invalid_choice", error_key)
        messages.setdefault("invalid", error_key)
        super().__init__(choices, error_messages=messages, **kwargs)

    def to_internal_value(self, data: Any) -> Any:
        # DRF looks the value up by ``str(data)``, which would let 1 match "1"; be strict.
        if not isinstance(data, str):
            self.fail("invalid_choice", input=data)
        return super().to_internal_value(data)


class KeyedDictField(KeyedMessages, serializers.DictField):
    """A JSON object whose *values* are validated later by whoever knows their schema (e.g. a
    request's ``details``, which only the chosen service's field definitions can judge)."""

    default_error_messages: ClassVar[dict[str, Any]] = {"not_a_dict": m.V_INVALID}


class StrictBooleanField(KeyedMessages, serializers.BooleanField):
    """Only JSON ``true``/``false``: not ``"true"``, ``"1"`` or ``1``."""

    def to_internal_value(self, data: Any) -> bool:
        if isinstance(data, bool):
            return data
        self.fail("invalid")
        raise AssertionError("unreachable")  # pragma: no cover - fail() always raises


class DepartmentIdsField(KeyedMessages, serializers.ListField):
    """A non-empty list of known department ids; duplicates are dropped, first occurrence wins."""

    def __init__(self, **kwargs: Any) -> None:
        messages: dict[str, Any] = {
            "not_a_list": m.V_DEPARTMENTS,
            "empty": m.V_DEPARTMENTS,
            "min_length": m.V_DEPARTMENTS,
            "max_length": m.V_DEPARTMENTS,
        }
        super().__init__(
            child=KeyedChoiceField(Department.choices, error_key=m.V_DEPARTMENTS),
            allow_empty=False,
            max_length=20,  # four departments exist; this only bounds a pathological payload
            error_messages=messages,
            **kwargs,
        )

    def run_child_validation(self, data: Any) -> Any:
        # An unknown id anywhere in the list is one problem *of the list*: reported as
        # ``departmentIds`` (what the form field is called), not as ``departmentIds.2``.
        try:
            return super().run_child_validation(data)
        except serializers.ValidationError:
            raise serializers.ValidationError(m.V_DEPARTMENTS) from None

    def to_internal_value(self, data: Any) -> list[str]:
        return list(dict.fromkeys(super().to_internal_value(data)))


def validate_input(serializer_class: type[serializers.Serializer], data: Any) -> dict[str, Any]:  # type: ignore[type-arg]
    """Validate a request body or query string with ``serializer_class``.

    A failure raises DRF's ``ValidationError``, which the exception handler turns into the
    contract's ``validation`` error (``errors`` = field → dictionary keys).
    """
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    validated: dict[str, Any] = serializer.validated_data
    return validated


# --- Documentation-only shapes shared by several apps (they also render ActorRefs) ------------


class LocalizedSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """``{fa, en}`` – domain content that carries its own translations."""

    fa = serializers.CharField()
    en = serializers.CharField()


class ActorRefSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """``{id, role, name: {fa, en}}`` – who did something, frozen at the time."""

    id = serializers.CharField()
    role = serializers.ChoiceField(choices=["customer", "staff", "admin"])
    name = LocalizedSerializer()
