"""Dynamic form fields: validating a field *definition*, and validating submitted *details* against
the definitions of the chosen service.

This is the Python twin of ``createDetailsSchema`` / ``toServiceDetails`` in the frontend
(``src/lib/validation/request.ts``): same rules, same message keys, same "unknown keys are
stripped, empty optional values are dropped" behaviour. A definition is plain JSON (stored in
``Service.field_definitions``):

    {"kind": "text",   "key": "purpose", "label": {"fa": …, "en": …}, "required": true,
     "maxLength": 120}
    {"kind": "number", "key": "amount",  "label": {…}, "required": true, "min": 1, "max": 9,
     "unit": {…}}
    {"kind": "select", "key": "term",    "label": {…}, "required": true,
     "options": [{"value": "12", "label": {…}}, …]}
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, TypeGuard

from django.core.exceptions import ValidationError

from apps.core import messages as m
from apps.core.text import contains_unstorable_characters

_KEY_SHAPE: Final = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
_COMMON_KEYS: Final = {"kind", "key", "label", "required"}
_ALLOWED_KEYS: Final[dict[str, set[str]]] = {
    "text": _COMMON_KEYS | {"maxLength"},
    "number": _COMMON_KEYS | {"min", "max", "unit"},
    "select": _COMMON_KEYS | {"options"},
}
_MAX_TEXT_LENGTH: Final = 2000


def _is_number(value: object) -> TypeGuard[int | float]:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def _is_localized(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"fa", "en"}
        and all(isinstance(text, str) and text.strip() for text in value.values())
    )


def find_definition_problems(definitions: object) -> list[str]:
    """Everything wrong with a list of field definitions (empty list = valid)."""
    if not isinstance(definitions, list):
        return ["field definitions must be a list"]
    problems: list[str] = []
    seen: set[str] = set()
    for index, definition in enumerate(definitions):
        where = f"field #{index}"
        if not isinstance(definition, dict):
            problems.append(f"{where}: must be an object")
            continue
        kind = definition.get("kind")
        key = definition.get("key")
        if kind not in _ALLOWED_KEYS:
            problems.append(f"{where}: kind must be one of {sorted(_ALLOWED_KEYS)}")
            continue
        if not isinstance(key, str) or not _KEY_SHAPE.fullmatch(key):
            problems.append(f"{where}: key must match {_KEY_SHAPE.pattern}")
        elif key in seen:
            problems.append(f"{where}: duplicate key {key!r}")
        else:
            seen.add(key)
            where = f"field {key!r}"
        if unknown := set(definition) - _ALLOWED_KEYS[kind]:
            problems.append(f"{where}: unknown properties {sorted(unknown)}")
        if not _is_localized(definition.get("label")):
            problems.append(f"{where}: label must be {{fa, en}} with non-empty text")
        if not isinstance(definition.get("required"), bool):
            problems.append(f"{where}: required must be true or false")

        if kind == "text":
            max_length = definition.get("maxLength")
            if (
                not isinstance(max_length, int)
                or isinstance(max_length, bool)
                or not 1 <= max_length <= _MAX_TEXT_LENGTH
            ):
                problems.append(f"{where}: maxLength must be an integer 1..{_MAX_TEXT_LENGTH}")
        elif kind == "number":
            low, high = definition.get("min"), definition.get("max")
            if not _is_number(low) or not _is_number(high):
                problems.append(f"{where}: min and max must be finite numbers")
            elif low > high:
                problems.append(f"{where}: min must not exceed max")
            if "unit" in definition and not _is_localized(definition["unit"]):
                problems.append(f"{where}: unit must be {{fa, en}} with non-empty text")
        else:  # select
            problems.extend(_option_problems(where, definition.get("options")))
    return problems


def _option_problems(where: str, options: object) -> list[str]:
    if not isinstance(options, list) or not options:
        return [f"{where}: options must be a non-empty list"]
    problems: list[str] = []
    values: set[str] = set()
    for option in options:
        if not isinstance(option, dict) or set(option) != {"value", "label"}:
            problems.append(f"{where}: each option must be {{value, label}}")
            continue
        value = option["value"]
        if not isinstance(value, str) or not value:
            problems.append(f"{where}: option value must be a non-empty string")
        elif value in values:
            problems.append(f"{where}: duplicate option value {value!r}")
        else:
            values.add(value)
        if not _is_localized(option["label"]):
            problems.append(f"{where}: option label must be {{fa, en}} with non-empty text")
    return problems


def validate_field_definitions(value: object) -> None:
    """Django validator for ``Service.field_definitions`` (used by ``full_clean`` and the sync)."""
    if problems := find_definition_problems(value):
        raise ValidationError(problems)


# --- Validating submitted details --------------------------------------------------------------

_SKIP: Final = object()  # "store nothing for this field"
Outcome = tuple[object, str | None]  # (value to store | _SKIP, error key | None)


def _text(definition: Mapping[str, Any], present: bool, value: object) -> Outcome:
    required = bool(definition["required"])
    if not present:
        return _SKIP, (m.V_REQUIRED if required else None)
    if not isinstance(value, str):
        return _SKIP, m.V_REQUIRED
    if contains_unstorable_characters(value):
        return _SKIP, m.V_INVALID
    text = value.strip()
    if len(text) > definition["maxLength"]:
        return _SKIP, m.V_TEXT_MAX
    if not text:
        return _SKIP, (m.V_REQUIRED if required else None)
    return text, None


def _number(definition: Mapping[str, Any], present: bool, value: object) -> Outcome:
    if not present:
        return _SKIP, (m.V_REQUIRED if definition["required"] else None)
    # bool is an int in Python but not a number in JSON; inf/nan can only come from "1e999".
    if not _is_number(value):
        return _SKIP, m.V_NUMBER_INVALID
    if value < definition["min"]:
        return _SKIP, m.V_NUMBER_MIN
    if value > definition["max"]:
        return _SKIP, m.V_NUMBER_MAX
    return value, None


def _select(definition: Mapping[str, Any], present: bool, value: object) -> Outcome:
    if not present:
        return _SKIP, (m.V_SELECT if definition["required"] else None)
    allowed = {option["value"] for option in definition["options"]}
    if not isinstance(value, str) or value not in allowed:
        return _SKIP, m.V_SELECT
    return value, None


_CHECKERS: Final = {"text": _text, "number": _number, "select": _select}


def clean_details(
    definitions: Sequence[Mapping[str, Any]], raw: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Validate ``raw`` against ``definitions``.

    Returns ``(cleaned, errors)``: ``cleaned`` holds only keys the definitions declare (anything
    else the client sent is silently dropped) and omits empty optional values; ``errors`` maps
    ``details.<key>`` to a list of message keys and is empty when everything is valid.
    """
    cleaned: dict[str, Any] = {}
    errors: dict[str, list[str]] = {}
    for definition in definitions:
        key = definition["key"]
        value, error = _CHECKERS[definition["kind"]](definition, key in raw, raw.get(key))
        if error is not None:
            errors[f"details.{key}"] = [error]
        elif value is not _SKIP:
            cleaned[key] = value
    return cleaned, errors
