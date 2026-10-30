"""Request body parsing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class StrictJSONParser(JSONParser):
    """DRF's JSON parser (which already rejects ``NaN``/``Infinity``), plus one hardening step:
    absurdly nested documents (``[[[[…``) make Python's ``json`` raise ``RecursionError``, which
    would otherwise surface as a 500. A client error is a 400."""

    def parse(
        self,
        stream: Any,
        media_type: str | None = None,
        parser_context: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError as exc:
            raise ParseError("JSON document is nested too deeply.") from exc
