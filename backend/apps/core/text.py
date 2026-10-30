"""Text safety helpers (no Django/DRF imports, so models may use them)."""

from __future__ import annotations

import re

#: NUL bytes and lone UTF-16 surrogates cannot be stored by PostgreSQL (``text`` / ``jsonb``);
#: letting them reach the database turns a client mistake into an unhandled 500.
_UNSTORABLE = re.compile("[\x00\ud800-\udfff]")


def contains_unstorable_characters(value: str) -> bool:
    return _UNSTORABLE.search(value) is not None
