"""Small database helpers shared by the services."""

from __future__ import annotations

from django.db import IntegrityError


def violated_constraint(error: IntegrityError) -> str | None:
    """Name of the constraint an ``IntegrityError`` violated (PostgreSQL ``diag``), if known.

    Services use this to translate a lost race against a unique index into the same domain error
    their pre-check would have raised, instead of letting it surface as a 500.
    """
    diagnostics = getattr(error.__cause__, "diag", None)
    name = getattr(diagnostics, "constraint_name", None)
    return name if isinstance(name, str) else None
