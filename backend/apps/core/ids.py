"""Identifier parsing."""

from __future__ import annotations

from uuid import UUID


def parse_uuid(value: object) -> UUID | None:
    """Parse a UUID that arrived as a URL segment or JSON string; ``None`` if it is anything else.

    Only the canonical 36-character form is accepted (Python's ``UUID()`` would also take braces,
    ``urn:uuid:`` prefixes and bare hex). A malformed id is simply "no such record": callers answer
    ``not_found`` exactly as they do for a well-formed id that does not exist, so ids can't be
    probed for shape.
    """
    if isinstance(value, UUID):
        return value
    if not isinstance(value, str) or len(value) != 36:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None
