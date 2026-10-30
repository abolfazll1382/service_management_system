"""OpenAPI post-processing: the shared error body.

Every non-2xx response of this API has the same shape (see :mod:`apps.core.exceptions`). Rather
than repeating it on each operation, one ``ApiError`` component is defined here and attached to
every operation as its ``default`` response, plus an explicit ``400`` where the operation takes
input and ``401`` where it needs a token.
"""

from __future__ import annotations

from typing import Any

from apps.core.exceptions import ApiErrorCode
from apps.core.messages import VALIDATION_KEYS

_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}

API_ERROR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Every error response. `code` is stable and machine-readable; `detail` is a sentence in "
        "the caller's language (`Accept-Language: fa` or `en`); `errors` maps a field (nested "
        "fields are dotted, e.g. `details.amount`) to the frontend's validation dictionary keys."
    ),
    "required": ["code", "detail", "errors"],
    "properties": {
        "code": {"type": "string", "enum": [code.value for code in ApiErrorCode]},
        "detail": {"type": "string"},
        "errors": {
            "type": "object",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(VALIDATION_KEYS)},
            },
            "example": {"nationalId": ["validation.nationalId.checksum"]},
        },
    },
}


def _error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}},
    }


def add_error_responses(
    result: dict[str, Any], generator: Any, request: Any, public: bool
) -> dict[str, Any]:
    """drf-spectacular ``POSTPROCESSING_HOOKS`` entry."""
    result.setdefault("components", {}).setdefault("schemas", {})["ApiError"] = API_ERROR_SCHEMA
    for path_item in result.get("paths", {}).values():
        for method, operation in path_item.items():
            if method not in _METHODS:
                continue
            responses = operation.setdefault("responses", {})
            takes_input = bool(operation.get("requestBody")) or any(
                parameter.get("in") == "query" for parameter in operation.get("parameters", [])
            )
            if takes_input:
                responses.setdefault(
                    "400", _error_response("Validation failed (`code: validation`).")
                )
            # ``security: [{}]`` is how OpenAPI says "no credentials needed": not a protected route.
            if any(requirement for requirement in operation.get("security", [])):
                responses.setdefault(
                    "401", _error_response("Missing, expired or revoked token (`unauthenticated`).")
                )
            responses.setdefault(
                "default",
                _error_response(
                    "Any other failure: see `code` (forbidden, not_found, conflict …)."
                ),
            )
    return result
