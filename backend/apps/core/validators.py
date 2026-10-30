"""Field validators for the shapes the frontend contract defines (see ``src/lib/validation``)."""

from __future__ import annotations

import re
from collections.abc import Callable

from rest_framework import serializers

from apps.core import messages as m
from apps.core.persian import is_valid_national_id

Validator = Callable[[str], None]


def pattern_validator(pattern: str, key: str) -> Validator:
    """Whole-string match.

    Never ``re.match`` with ``$``: ``$`` also matches before a trailing newline.
    """
    compiled = re.compile(pattern)

    def validate(value: str) -> None:
        if not compiled.fullmatch(value):
            raise serializers.ValidationError(key)

    return validate


def national_id_validator(*, check_digit: bool) -> Validator:
    """Ten ASCII digits and, unless ``check_digit`` is off, a valid modulo-11 check digit.

    Only the first failure is reported: a checksum complaint about "123" would be noise.
    """
    shape = pattern_validator(r"[0-9]{10}", m.V_NATIONAL_ID_FORMAT)

    def validate(value: str) -> None:
        shape(value)
        if check_digit and not is_valid_national_id(value):
            raise serializers.ValidationError(m.V_NATIONAL_ID_CHECKSUM)

    return validate


phone_validator: Validator = pattern_validator(r"09[0-9]{9}", m.V_PHONE)
postal_code_validator: Validator = pattern_validator(r"[0-9]{10}", m.V_POSTAL_CODE)
username_validator: Validator = pattern_validator(r"[a-z][a-z0-9_]{2,19}", m.V_USERNAME)


def new_password_validator(value: str) -> None:
    """At least one ASCII letter and one ASCII digit (length is checked by the field)."""
    if not re.search(r"[A-Za-z]", value) or not re.search(r"[0-9]", value):
        raise serializers.ValidationError(m.V_PASSWORD_MIX)
