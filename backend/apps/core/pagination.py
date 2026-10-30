"""Offset pagination with the frontend's envelope: ``{items, total, page, pageSize}``.

DRF's ``PageNumberPagination`` answers 404 for a page past the end; the frontend contract is an
empty ``items`` list (with the real ``total``), so pagination is done explicitly here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar

from django.db.models import Model, QuerySet
from rest_framework import serializers

from apps.core.serializers import KeyedIntegerField


@dataclass(frozen=True, slots=True)
class Page[T]:
    """One page of results plus the numbers a pager needs."""

    items: list[T]
    total: int
    page: int
    page_size: int

    def envelope(self, serialized_items: Iterable[Any], **extra: Any) -> dict[str, Any]:
        """The wire form: ``{items, total, page, pageSize, ...extra}``.

        ``extra`` carries endpoint-specific additions such as ``counts``.
        """
        return {
            "items": list(serialized_items),
            "total": self.total,
            "page": self.page,
            "pageSize": self.page_size,
            **extra,
        }


def paginate[M: Model](queryset: QuerySet[M], *, page: int, page_size: int) -> Page[M]:
    """Slice ``queryset`` (which must already be ordered deterministically)."""
    total = queryset.count()
    offset = (page - 1) * page_size
    items = list(queryset[offset : offset + page_size]) if offset < total else []
    return Page(items=items, total=total, page=page, page_size=page_size)


class PageQuerySerializer(serializers.Serializer):  # type: ignore[type-arg]
    """``?page=&pageSize=`` – subclasses set their own default and ceiling."""

    default_page_size: ClassVar[int] = 10
    max_page_size: ClassVar[int] = 50

    def get_fields(self) -> dict[str, Any]:
        fields = dict(super().get_fields())
        fields["page"] = KeyedIntegerField(min_value=1, required=False, default=1)
        fields["pageSize"] = KeyedIntegerField(
            min_value=1,
            max_value=self.max_page_size,
            required=False,
            default=self.default_page_size,
        )
        return fields
